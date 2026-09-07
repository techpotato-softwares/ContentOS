"""Hybrid AI billing metering — credentials, quota, BYOK, stub, usage events."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers/shared/python/src"))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("IS_LOCAL", "true")
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("AI_PROVIDER", "stub")
os.environ.setdefault("RECORD_STUB_USAGE", "true")

from billing import apply_billing_defaults, PLAN_CATALOG  # noqa: E402
from billing.ai_billing import (  # noqa: E402
    QuotaExceededError,
    assert_and_consume_quota,
    assert_platform_quota,
    list_usage_events_for_tenant,
    meter_ai_success,
    resolve_ai_credentials,
)
from billing.ai_secrets import put_tenant_ai_secrets, clear_platform_ai_secrets_cache  # noqa: E402
from database.models import AiUsageEvent, Tenant  # noqa: E402
from middleware.error_handler import create_error_response  # noqa: E402
import database.models  # noqa: F401,E402


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'meter.db'}"
    engine = create_engine(db_url)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.setenv("AI_PROVIDER", "stub")
    monkeypatch.setenv("RECORD_STUB_USAGE", "true")
    monkeypatch.setenv("BILLING_SKIP_ENSURE", "true")
    clear_platform_ai_secrets_cache()
    with Session(engine) as session:
        yield session


def _tenant(session, **kwargs) -> Tenant:
    t = Tenant(name=kwargs.pop("name", "T"), slug=kwargs.pop("slug", f"t-{os.urandom(3).hex()}"))
    apply_billing_defaults(t)
    for k, v in kwargs.items():
        setattr(t, k, v)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def test_plan_catalog_present():
    assert "starter" in PLAN_CATALOG
    assert PLAN_CATALOG["starter"].ai_posts_quota_monthly == 40


def test_platform_quota_consume_and_event(db_session):
    t = _tenant(db_session, plan="starter", ai_billing_mode="platform", ai_posts_quota_monthly=5)
    creds = resolve_ai_credentials(t, preferred_provider="stub")
    assert creds.mode == "platform"
    assert creds.source == "stub"
    assert_platform_quota(t, 2)
    meter_ai_success(
        db_session,
        tenant=t,
        kind="generate_batch",
        units=2,
        model="stub",
        provider="stub",
        creds=creds,
    )
    db_session.commit()
    db_session.refresh(t)
    assert t.ai_posts_used_month == 2
    events = db_session.exec(select(AiUsageEvent).where(AiUsageEvent.tenant_id == t.tenant_id)).all()
    assert len(events) == 1
    assert events[0].kind == "generate_batch"
    assert events[0].units == 2


def test_over_quota_returns_upgrade_payload(db_session):
    t = _tenant(
        db_session,
        plan="starter",
        ai_billing_mode="platform",
        ai_posts_quota_monthly=2,
        ai_posts_used_month=2,
        ai_usage_month=__import__("billing.ai_billing", fromlist=["current_usage_month"]).current_usage_month(),
    )
    with pytest.raises(QuotaExceededError) as exc:
        assert_platform_quota(t, 1)
    err = exc.value
    assert err.status_code == 402
    assert err.code == "QUOTA_EXCEEDED"
    assert err.upgrade is True
    assert err.plan["id"] == "starter"
    assert err.usage["remaining"] == 0
    body = json.loads(create_error_response(err)["body"])
    assert body["upgrade"] is True
    assert body["plan"]["id"] == "starter"
    assert body["usage"]["usedThisMonth"] == 2
    assert create_error_response(err)["statusCode"] == 402


def test_byok_skips_quota_but_records_event(db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.delenv("AI_PROVIDER", raising=False)  # not stub — exercise BYOK path
    # Force non-stub resolve by preferred_provider openai with local keys
    t = _tenant(
        db_session,
        plan="growth",
        ai_billing_mode="byok",
        ai_posts_quota_monthly=150,
        ai_posts_used_month=0,
    )
    arn = put_tenant_ai_secrets(t.tenant_id, {"OPENAI_API_KEY": "sk-test-byok"})
    t.ai_secret_arn = arn
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    with patch("billing.ai_billing._is_stub_provider", return_value=False):
        creds = resolve_ai_credentials(t, preferred_provider="openai")
        assert creds.mode == "byok"
        assert creds.source == "byok"
        assert creds.openai_api_key == "sk-test-byok"
        # Would fail on platform with used=150/limit=0 style; here quota unused
        t.ai_posts_used_month = 150
        t.ai_usage_month = __import__(
            "billing.ai_billing", fromlist=["current_usage_month"]
        ).current_usage_month()
        assert_platform_quota(t, 10)  # no-op for byok
        meter_ai_success(
            db_session,
            tenant=t,
            kind="chat",
            units=1,
            model="gpt-4o-mini",
            provider="openai",
            creds=creds,
        )
        db_session.commit()
        db_session.refresh(t)
        assert t.ai_posts_used_month == 150  # unchanged
    events = list_usage_events_for_tenant(db_session, t.tenant_id)
    assert len(events) == 1
    assert events[0]["kind"] == "chat"
    assert events[0]["meta"]["billingMode"] == "byok"


def test_byok_not_allowed_on_starter(db_session, monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    t = _tenant(db_session, plan="starter", ai_billing_mode="byok")
    with patch("billing.ai_billing._is_stub_provider", return_value=False):
        with pytest.raises(Exception) as exc:
            resolve_ai_credentials(t, preferred_provider="openai")
    assert getattr(exc.value, "code", None) == "BYOK_NOT_ALLOWED"


def test_stub_provider_offline_and_logs_usage(db_session, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "stub")
    monkeypatch.setenv("RECORD_STUB_USAGE", "true")
    t = _tenant(db_session)
    from modules.agent.src.providers import get_provider

    provider = get_provider("stub")
    reply = provider.chat("hello", "pack", [])
    assert "generate" in reply.lower() or "stub" in reply.lower() or len(reply) > 0
    creds = resolve_ai_credentials(t, preferred_provider="stub")
    meter_ai_success(
        db_session,
        tenant=t,
        kind="chat",
        units=1,
        provider="stub",
        creds=creds,
    )
    db_session.commit()
    assert t.ai_posts_used_month == 1
    assert list_usage_events_for_tenant(db_session, t.tenant_id)


def test_usage_events_tenant_scoped(db_session):
    a = _tenant(db_session, slug="scope-a")
    b = _tenant(db_session, slug="scope-b")
    meter_ai_success(db_session, tenant=a, kind="chat", units=1, provider="stub")
    meter_ai_success(db_session, tenant=b, kind="generate_batch", units=3, provider="stub")
    db_session.commit()
    a_events = list_usage_events_for_tenant(db_session, a.tenant_id)
    b_events = list_usage_events_for_tenant(db_session, b.tenant_id)
    assert len(a_events) == 1 and a_events[0]["kind"] == "chat"
    assert len(b_events) == 1 and b_events[0]["units"] == 3


def test_assert_and_consume_quota_helper(db_session):
    t = _tenant(db_session, ai_posts_quota_monthly=3, ai_posts_used_month=0)
    assert_and_consume_quota(db_session, t, 2)
    db_session.commit()
    db_session.refresh(t)
    assert t.ai_posts_used_month == 2
    with pytest.raises(QuotaExceededError):
        assert_and_consume_quota(db_session, t, 2)
