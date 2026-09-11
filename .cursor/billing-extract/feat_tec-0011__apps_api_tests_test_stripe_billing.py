"""Stripe billing: checkout/portal/webhook sync, soft-lock, BYOK exception, idempotency."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_dummy"
os.environ["STRIPE_PRICE_STARTER"] = "price_starter_test"
os.environ["STRIPE_PRICE_GROWTH"] = "price_growth_test"
os.environ["STRIPE_PRICE_SCALE"] = "price_scale_test"
os.environ["STRIPE_PRICE_AGENCY"] = "price_agency_test"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import StripeWebhookEvent, Tenant
from middleware.error_handler import AppError
from utils.ai_billing import (
    assert_platform_billing_ok,
    ensure_monthly_quota,
    apply_plan_to_tenant,
)
from utils.stripe_billing import process_stripe_event, construct_webhook_event
from utils.stripe_secrets import clear_stripe_secrets_cache, price_id_to_plan_tier
from modules.tenants.src.controllers.billing_controller import BillingController


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'billing.db'}"
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
        clear_stripe_secrets_cache()
        # reset ensure flag so schema helper can run against this engine
        import utils.tenant_billing_schema as tbs

        tbs._ensured = False
        yield factory

    db_mod._engine = None
    db_mod._SessionLocal = None
    clear_stripe_secrets_cache()
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
        stripe_customer_id=kwargs.get("stripe_customer_id"),
        stripe_subscription_id=kwargs.get("stripe_subscription_id"),
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


def test_price_maps_to_plan_catalog():
    assert price_id_to_plan_tier("price_growth_test") == "growth"
    assert price_id_to_plan_tier("price_unknown") is None


def test_apply_plan_sets_quota(db_session):
    with db_session() as session:
        t = _tenant(session)
        apply_plan_to_tenant(t, "growth")
        session.add(t)
        session.commit()
        session.refresh(t)
        assert t.plan_tier == "growth"
        assert t.ai_posts_quota_monthly == 150


def test_soft_lock_platform_past_due(db_session):
    with db_session() as session:
        t = _tenant(session, billing_status="past_due", ai_billing_mode="platform")
        with pytest.raises(AppError) as ei:
            assert_platform_billing_ok(t)
        assert ei.value.status_code == 402
        assert ei.value.code == "billing_required"


def test_byok_not_soft_locked(db_session):
    with db_session() as session:
        t = _tenant(session, billing_status="past_due", ai_billing_mode="byok")
        assert_platform_billing_ok(t)  # must not raise
        ensure_monthly_quota(t, 5)  # BYOK: no quota consume
        assert t.ai_posts_used_month == 0


def test_checkout_session_creates_stripe_customer(db_session):
    with db_session() as session:
        t = _tenant(session)

    fake_stripe = MagicMock()
    fake_stripe.Customer.create.return_value = {"id": "cus_test_1"}
    fake_stripe.checkout.Session.create.return_value = {
        "id": "cs_test_1",
        "url": "https://checkout.stripe.test/session",
    }

    with patch("utils.stripe_billing.get_stripe", return_value=fake_stripe), patch(
        "utils.stripe_secrets.get_stripe", return_value=fake_stripe
    ):
        ctrl = BillingController()
        resp = ctrl.checkout_session(
            {"planTier": "growth"},
            user=_admin_user(t.tenant_id),
        )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])["data"]
    assert body["url"].startswith("https://checkout.stripe.test")
    with db_session() as session:
        refreshed = session.get(Tenant, t.tenant_id)
        assert refreshed.stripe_customer_id == "cus_test_1"


def test_portal_session_requires_customer(db_session):
    from middleware.error_handler import ValidationError

    with db_session() as session:
        t = _tenant(session, stripe_customer_id=None)
    ctrl = BillingController()
    with pytest.raises(ValidationError):
        ctrl.portal_session({}, user=_admin_user(t.tenant_id))


def test_portal_session_ok(db_session):
    with db_session() as session:
        t = _tenant(session, stripe_customer_id="cus_abc")

    fake_stripe = MagicMock()
    fake_stripe.billing_portal.Session.create.return_value = {
        "url": "https://billing.stripe.test/portal"
    }
    with patch("utils.stripe_billing.get_stripe", return_value=fake_stripe):
        ctrl = BillingController()
        resp = ctrl.portal_session({}, user=_admin_user(t.tenant_id))
    assert resp["statusCode"] == 200
    assert "billing.stripe.test" in json.loads(resp["body"])["data"]["url"]


def test_webhook_signature_invalid(db_session):
    with patch("utils.stripe_billing.get_stripe") as gs:
        stripe_mod = MagicMock()
        stripe_mod.Webhook.construct_event.side_effect = Exception("bad sig")
        gs.return_value = stripe_mod
        with pytest.raises(AppError) as ei:
            construct_webhook_event(b"{}", "t=1,v1=abc")
        assert ei.value.code == "STRIPE_SIGNATURE_INVALID"


def test_webhook_payment_failed_sets_past_due(db_session):
    with db_session() as session:
        t = _tenant(session, stripe_customer_id="cus_fail", billing_status="active")

    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "invoice.payment_failed",
        "data": {"object": {"customer": "cus_fail", "subscription": "sub_x"}},
    }
    with db_session() as session:
        summary = process_stripe_event(session, event)
        session.commit()
        assert summary["duplicate"] is False
        refreshed = session.get(Tenant, t.tenant_id)
        assert refreshed.billing_status == "past_due"


def test_webhook_subscription_updated_syncs_plan(db_session):
    with db_session() as session:
        t = _tenant(
            session,
            stripe_customer_id="cus_up",
            plan_tier="starter",
            ai_posts_quota_monthly=40,
        )

    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_up",
                "customer": "cus_up",
                "status": "active",
                "metadata": {"tenant_id": str(t.tenant_id)},
                "items": {"data": [{"price": {"id": "price_growth_test"}}]},
            }
        },
    }
    with db_session() as session:
        process_stripe_event(session, event)
        session.commit()
        refreshed = session.get(Tenant, t.tenant_id)
        assert refreshed.plan_tier == "growth"
        assert refreshed.ai_posts_quota_monthly == 150
        assert refreshed.billing_status == "active"
        assert refreshed.stripe_subscription_id == "sub_up"


def test_webhook_idempotent(db_session):
    with db_session() as session:
        t = _tenant(session, stripe_customer_id="cus_idemp", billing_status="active")

    event = {
        "id": "evt_idempotent_1",
        "type": "invoice.payment_failed",
        "data": {"object": {"customer": "cus_idemp"}},
    }
    with db_session() as session:
        first = process_stripe_event(session, event)
        session.commit()
        assert first["duplicate"] is False

    with db_session() as session:
        second = process_stripe_event(session, event)
        session.commit()
        assert second["duplicate"] is True
        rows = session.exec(select(StripeWebhookEvent)).all()
        assert len(rows) == 1


def test_checkout_completed_retrieves_subscription(db_session):
    with db_session() as session:
        t = _tenant(session, stripe_customer_id="cus_co")

    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = {
        "id": "sub_co",
        "customer": "cus_co",
        "status": "active",
        "metadata": {"tenant_id": str(t.tenant_id), "plan_tier": "scale"},
        "items": {"data": [{"price": {"id": "price_scale_test"}}]},
    }
    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_co",
                "subscription": "sub_co",
                "client_reference_id": str(t.tenant_id),
                "metadata": {"tenant_id": str(t.tenant_id), "plan_tier": "scale"},
            }
        },
    }
    with patch("utils.stripe_billing.get_stripe", return_value=fake_stripe):
        with db_session() as session:
            process_stripe_event(session, event)
            session.commit()
            refreshed = session.get(Tenant, t.tenant_id)
            assert refreshed.plan_tier == "scale"
            assert refreshed.billing_status == "active"
