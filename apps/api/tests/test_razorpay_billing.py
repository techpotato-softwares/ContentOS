"""Razorpay INR billing: mapping, webhooks, soft-lock, double-billing, secrets."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_dummy"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_secret_dummy"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec_razorpay_test"
os.environ["RAZORPAY_PLAN_STARTER"] = "plan_starter_test"
os.environ["RAZORPAY_PLAN_GROWTH"] = "plan_growth_test"
os.environ["RAZORPAY_PLAN_SCALE"] = "plan_scale_test"
os.environ["RAZORPAY_PLAN_AGENCY"] = "plan_agency_test"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_dummy"
os.environ["STRIPE_PRICE_STARTER"] = "price_starter_test"
os.environ["STRIPE_PRICE_GROWTH"] = "price_growth_test"
os.environ["STRIPE_PRICE_SCALE"] = "price_scale_test"
os.environ["STRIPE_PRICE_AGENCY"] = "price_agency_test"
os.environ.pop("DATABASE_URL", None)

import database as db_mod
from database.models import RazorpayWebhookEvent, Tenant
from middleware.error_handler import AppError, ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select
from utils.ai_billing import (
    PLAN_CATALOG,
    assert_can_subscribe,
    assert_platform_billing_ok,
    catalog_public,
    ensure_monthly_quota,
    preferred_gateway_for_currency,
)
from utils.razorpay_billing import (
    create_subscription,
    process_razorpay_event,
    verify_webhook_signature,
)
from utils.razorpay_secrets import (
    clear_razorpay_secrets_cache,
    get_razorpay_secrets,
    plan_id_to_plan_tier,
)

from modules.tenants.src.controllers.billing_controller import BillingController


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'rzp.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    db_mod._engine = engine
    db_mod._SessionLocal = factory

    def _get_session():
        return factory()

    with patch.object(db_mod, "get_session", _get_session), patch.object(
        db_mod, "get_engine", lambda: engine
    ), patch(
        "modules.tenants.src.controllers.billing_controller.get_session", _get_session
    ), patch(
        "utils.tenant_billing_schema.get_engine", lambda: engine
    ):
        clear_razorpay_secrets_cache()
        import utils.tenant_billing_schema as tbs

        tbs._ensured = False
        yield factory

    db_mod._engine = None
    db_mod._SessionLocal = None
    clear_razorpay_secrets_cache()
    import utils.tenant_billing_schema as tbs

    tbs._ensured = False


def _tenant(session, **kwargs) -> Tenant:
    t = Tenant(
        name=kwargs.get("name", f"Co {uuid.uuid4().hex[:6]}"),
        slug=kwargs.get("slug", f"co-{uuid.uuid4().hex[:8]}"),
        ai_billing_mode=kwargs.get("ai_billing_mode", "platform"),
        plan_tier=kwargs.get("plan_tier", "starter"),
        ai_posts_quota_monthly=kwargs.get("ai_posts_quota_monthly", 40),
        ai_posts_used_month=kwargs.get("ai_posts_used_month", 0),
        billing_status=kwargs.get("billing_status", "none"),
        billing_gateway=kwargs.get("billing_gateway"),
        stripe_customer_id=kwargs.get("stripe_customer_id"),
        stripe_subscription_id=kwargs.get("stripe_subscription_id"),
        razorpay_customer_id=kwargs.get("razorpay_customer_id"),
        razorpay_subscription_id=kwargs.get("razorpay_subscription_id"),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _admin_user(tenant_id: int) -> dict:
    return {
        "userId": 1,
        "tenantId": tenant_id,
        "email": "admin@example.com",
        "permissions": ["tenant:admin"],
        "modulesEnabled": ["platform", "tenants", "agent", "publishing"],
    }


def _sign(body: bytes) -> str:
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"].encode("utf-8")
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def test_inr_prices_match_documented_mapping():
    expected = {
        "starter": (49, 4099),
        "growth": (149, 12499),
        "scale": (399, 33499),
        "agency": (399, 33499),
    }
    for tier, (usd, inr) in expected.items():
        assert PLAN_CATALOG[tier]["monthly_usd"] == usd
        assert PLAN_CATALOG[tier]["monthly_inr"] == inr
    public = {p["id"]: p for p in catalog_public()}
    assert public["starter"]["monthlyInr"] == 4099
    assert preferred_gateway_for_currency("inr") == "razorpay"
    assert preferred_gateway_for_currency("usd") == "stripe"


def test_plan_id_maps_to_tier():
    assert plan_id_to_plan_tier("plan_growth_test") == "growth"
    assert plan_id_to_plan_tier("plan_unknown") is None


def test_subscription_creation_sets_gateway(db_session):
    factory = db_session
    with factory() as session:
        t = _tenant(session)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "sub_test_1",
        "short_url": "https://rzp.io/i/test",
    }

    with patch("utils.razorpay_billing.httpx.Client") as Client:
        client = Client.return_value.__enter__.return_value
        # customer create then subscription
        client.request.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "cust_1"}),
            mock_resp,
        ]
        with factory() as session:
            tenant = session.get(Tenant, t.tenant_id)
            result = create_subscription(
                session, tenant=tenant, plan_tier="growth", customer_email="a@b.com"
            )
            session.commit()
            session.refresh(tenant)
            assert result["url"].startswith("https://rzp.io")
            assert result["currency"] == "INR"
            assert result["amountInr"] == "12499"
            assert tenant.razorpay_subscription_id == "sub_test_1"
            assert tenant.billing_gateway == "razorpay"
            assert tenant.razorpay_customer_id == "cust_1"


def test_webhook_signature_valid_and_invalid():
    body = json.dumps({"event": "subscription.activated", "payload": {}}).encode()
    event = verify_webhook_signature(body, _sign(body))
    assert event["event"] == "subscription.activated"
    with pytest.raises(AppError) as ei:
        verify_webhook_signature(body, "bad_signature")
    assert ei.value.code == "RAZORPAY_SIGNATURE_INVALID"
    with pytest.raises(AppError) as ei2:
        verify_webhook_signature(body, None)
    assert ei2.value.code == "RAZORPAY_SIGNATURE_MISSING"


def test_webhook_activates_plan_and_quota(db_session):
    factory = db_session
    with factory() as session:
        t = _tenant(
            session,
            razorpay_customer_id="cust_act",
            plan_tier="starter",
            ai_posts_quota_monthly=40,
        )
        event = {
            "id": "evt_act_1",
            "event": "subscription.activated",
            "created_at": 1,
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_act",
                        "customer_id": "cust_act",
                        "plan_id": "plan_growth_test",
                        "status": "active",
                        "notes": {"tenant_id": str(t.tenant_id), "plan_tier": "growth"},
                    }
                }
            },
        }
        summary = process_razorpay_event(session, event)
        session.commit()
        assert summary["duplicate"] is False
        refreshed = session.get(Tenant, t.tenant_id)
        assert refreshed.plan_tier == "growth"
        assert refreshed.ai_posts_quota_monthly == 150
        assert refreshed.billing_status == "active"
        assert refreshed.billing_gateway == "razorpay"
        assert refreshed.razorpay_subscription_id == "sub_act"


def test_webhook_idempotent(db_session):
    factory = db_session
    with factory() as session:
        t = _tenant(session, razorpay_customer_id="cust_idemp")
        event = {
            "id": "evt_dup",
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_dup",
                        "customer_id": "cust_idemp",
                        "plan_id": "plan_starter_test",
                        "status": "active",
                        "notes": {"tenant_id": str(t.tenant_id)},
                    }
                }
            },
        }
        first = process_razorpay_event(session, event)
        session.commit()
        second = process_razorpay_event(session, event)
        session.commit()
        assert first["duplicate"] is False
        assert second["duplicate"] is True
        rows = session.exec(select(RazorpayWebhookEvent)).all()
        assert len(rows) == 1


def test_payment_failure_soft_lock(db_session):
    factory = db_session
    with factory() as session:
        t = _tenant(
            session,
            billing_status="active",
            billing_gateway="razorpay",
            razorpay_subscription_id="sub_fail",
            ai_billing_mode="platform",
        )
        event = {
            "id": "evt_fail",
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_fail",
                        "subscription_id": "sub_fail",
                        "notes": {"tenant_id": str(t.tenant_id)},
                    }
                }
            },
        }
        process_razorpay_event(session, event)
        session.commit()
        refreshed = session.get(Tenant, t.tenant_id)
        assert refreshed.billing_status == "past_due"
        with pytest.raises(AppError) as ei:
            assert_platform_billing_ok(refreshed)
        assert ei.value.code == "billing_required"
        with pytest.raises(AppError):
            ensure_monthly_quota(refreshed, 1)


def test_double_billing_prevention(db_session):
    factory = db_session
    with factory() as session:
        t = _tenant(
            session,
            billing_status="active",
            billing_gateway="stripe",
            stripe_subscription_id="sub_stripe",
        )
        with pytest.raises(ValidationError):
            assert_can_subscribe(t, "razorpay")

        t2 = _tenant(
            session,
            billing_status="active",
            billing_gateway="razorpay",
            razorpay_subscription_id="sub_rzp",
            slug=f"co-{uuid.uuid4().hex[:8]}",
        )
        with pytest.raises(ValidationError):
            assert_can_subscribe(t2, "stripe")

        # same gateway OK
        assert_can_subscribe(t, "stripe")


def test_gateway_switch_requires_cancel(db_session):
    factory = db_session
    with factory() as session:
        t = _tenant(
            session,
            billing_status="active",
            billing_gateway="stripe",
            stripe_subscription_id="sub_s",
        )
        with pytest.raises(ValidationError) as ei:
            assert_can_subscribe(t, "razorpay")
        assert "Cancel" in str(ei.value) or "cancel" in str(ei.value).lower() or "already" in str(
            ei.value
        ).lower()

        # After cancel
        t.billing_status = "canceled"
        t.stripe_subscription_id = None
        t.billing_gateway = None
        assert_can_subscribe(t, "razorpay")


def test_secrets_not_in_public_catalog_or_summary(db_session):
    factory = db_session
    secrets = get_razorpay_secrets()
    assert secrets.key_secret
    public = json.dumps(catalog_public())
    assert secrets.key_secret not in public
    assert secrets.webhook_secret not in public
    assert "rzp_secret" not in public

    with factory() as session:
        t = _tenant(session)
        ctrl = BillingController()
        with patch(
            "modules.tenants.src.controllers.billing_controller.resolve_tenant_id",
            return_value=t.tenant_id,
        ), patch(
            "modules.tenants.src.controllers.billing_controller.require_user",
            return_value=_admin_user(t.tenant_id),
        ):
            resp = ctrl.billing_summary(
                user=_admin_user(t.tenant_id),
                event={"queryStringParameters": {"currency": "inr"}},
            )
    body = resp["body"] if isinstance(resp, dict) and "body" in resp else json.dumps(resp)
    if isinstance(body, dict):
        body = json.dumps(body)
    assert secrets.key_secret not in body
    assert "RAZORPAY_KEY_SECRET" not in body
    data = json.loads(body) if isinstance(body, str) else body
    payload = data.get("data") or data
    assert payload["preferredGateway"] == "razorpay"
    assert payload["monthlyInr"] == 4099


def test_controller_rejects_invalid_razorpay_webhook(db_session):
    ctrl = BillingController()
    event = {
        "body": json.dumps({"event": "subscription.activated"}),
        "headers": {"X-Razorpay-Signature": "nope"},
    }
    with pytest.raises(AppError) as ei:
        ctrl.razorpay_webhook(event=event)
    assert ei.value.code == "RAZORPAY_SIGNATURE_INVALID"
