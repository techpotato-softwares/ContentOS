"""AI settings GET/PUT: BYOK gates, key redaction, plan edit rejection."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel

import database as db_mod
from database.models import Tenant
from middleware.error_handler import AppError, ValidationError
from modules.tenants.src.controllers.tenants_controller import TenantsController
from utils.ai_billing import ensure_monthly_quota
from utils.ai_secrets import peek_tenant_ai_key_flags


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'ai_settings.db'}"
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
        "modules.tenants.src.controllers.tenants_controller.get_session", _get_session
    ), patch(
        "utils.tenant_billing_schema.get_engine", lambda: engine
    ), patch(
        "utils.ai_secrets._local_data_dir", lambda: tmp_path / "tenant_ai"
    ):
        import utils.tenant_billing_schema as tbs

        tbs._ensured = False
        (tmp_path / "tenant_ai").mkdir(parents=True, exist_ok=True)
        yield factory

    db_mod._engine = None
    db_mod._SessionLocal = None
    import utils.tenant_billing_schema as tbs

    tbs._ensured = False


def _tenant(session, **kwargs) -> Tenant:
    t = Tenant(
        name=kwargs.get("name", f"Co {uuid.uuid4().hex[:6]}"),
        slug=kwargs.get("slug", f"co-{uuid.uuid4().hex[:8]}"),
        ai_billing_mode=kwargs.get("ai_billing_mode", "platform"),
        plan_tier=kwargs.get("plan_tier", "starter"),
        ai_posts_quota_monthly=kwargs.get("ai_posts_quota_monthly", 40),
        ai_posts_used_month=kwargs.get("ai_posts_used_month", 12),
        ai_usage_month=kwargs.get("ai_usage_month", "2026-09"),
        ai_secret_arn=kwargs.get("ai_secret_arn"),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _user(tenant_id: int) -> dict:
    return {
        "userId": 1,
        "tenantId": tenant_id,
        "email": "admin@example.com",
        "permissions": ["training:manage", "tenant:admin"],
    }


def _body(resp: dict) -> dict:
    return json.loads(resp["body"])


def test_get_ai_settings_shape(db_session):
    with db_session() as session:
        t = _tenant(session, ai_usage_month="2026-09", ai_posts_used_month=12)
        tid = t.tenant_id

    ctrl = TenantsController()
    with patch("utils.ai_billing.current_usage_month", return_value="2026-09"):
        resp = ctrl.get_ai_settings(user=_user(tid))
    data = _body(resp)["data"]
    assert data["aiBillingMode"] == "platform"
    assert data["planTier"] == "starter"
    assert data["byokAllowed"] is False
    assert data["quota"]["monthlyLimit"] == 40
    assert data["quota"]["usedThisMonth"] == 12
    assert data["quota"]["remaining"] == 28
    assert data["keys"] == {"openaiConfigured": False, "geminiConfigured": False}
    assert any(p["id"] == "growth" and p["byokAllowed"] for p in data["plans"])
    blob = json.dumps(data)
    assert "sk-" not in blob
    assert "OPENAI" not in blob


def test_starter_cannot_enable_byok(db_session):
    with db_session() as session:
        t = _tenant(session, plan_tier="starter")
        tid = t.tenant_id

    ctrl = TenantsController()
    with pytest.raises(AppError) as exc:
        ctrl.put_ai_settings(
            {"aiBillingMode": "byok", "openaiApiKey": "sk-test-key"},
            user=_user(tid),
        )
    assert exc.value.code == "BYOK_NOT_ALLOWED"
    assert exc.value.status_code == 403


def test_growth_can_save_and_clear_byok(db_session):
    with db_session() as session:
        t = _tenant(session, plan_tier="growth")
        tid = t.tenant_id

    ctrl = TenantsController()
    resp = ctrl.put_ai_settings(
        {
            "aiBillingMode": "byok",
            "openaiApiKey": "sk-live-secret-should-not-leak",
            "geminiApiKey": "AIza-test-gemini",
        },
        user=_user(tid),
    )
    data = _body(resp)["data"]
    assert data["aiBillingMode"] == "byok"
    assert data["byokAllowed"] is True
    assert data["keys"]["openaiConfigured"] is True
    assert data["keys"]["geminiConfigured"] is True
    assert "sk-live" not in json.dumps(data)
    assert "AIza" not in json.dumps(data)

    with db_session() as session:
        t = session.get(Tenant, tid)
        assert t.ai_secret_arn
        flags = peek_tenant_ai_key_flags(tid, t.ai_secret_arn)
        assert flags["openaiConfigured"] is True

    cleared = ctrl.put_ai_settings({"clearOpenai": True}, user=_user(tid))
    cleared_data = _body(cleared)["data"]
    assert cleared_data["keys"]["openaiConfigured"] is False
    assert cleared_data["keys"]["geminiConfigured"] is True
    assert cleared_data["aiBillingMode"] == "byok"

    # Clearing the last key while staying on BYOK must fail
    with pytest.raises(AppError) as exc:
        ctrl.put_ai_settings({"clearGemini": True}, user=_user(tid))
    assert exc.value.code == "BYOK_KEYS_MISSING"

    # Switch back to platform, then clear remaining key
    back = ctrl.put_ai_settings(
        {"aiBillingMode": "platform", "clearGemini": True},
        user=_user(tid),
    )
    back_data = _body(back)["data"]
    assert back_data["aiBillingMode"] == "platform"
    assert back_data["keys"]["geminiConfigured"] is False
    assert back_data["keys"]["openaiConfigured"] is False


def test_byok_keys_missing_when_enabling_without_keys(db_session):
    with db_session() as session:
        t = _tenant(session, plan_tier="growth")
        tid = t.tenant_id

    ctrl = TenantsController()
    with pytest.raises(AppError) as exc:
        ctrl.put_ai_settings({"aiBillingMode": "byok"}, user=_user(tid))
    assert exc.value.code == "BYOK_KEYS_MISSING"
    assert exc.value.status_code == 400


def test_rejects_plan_tier_edit_on_ai_settings(db_session):
    with db_session() as session:
        t = _tenant(session, plan_tier="starter")
        tid = t.tenant_id

    ctrl = TenantsController()
    with pytest.raises(ValidationError):
        ctrl.put_ai_settings({"planTier": "agency"}, user=_user(tid))


def test_quota_exceeded_code(db_session):
    with db_session() as session:
        t = _tenant(
            session,
            plan_tier="starter",
            ai_posts_quota_monthly=1,
            ai_posts_used_month=1,
            ai_usage_month="2026-09",
        )
        with patch("utils.ai_billing.current_usage_month", return_value="2026-09"):
            with pytest.raises(AppError) as exc:
                ensure_monthly_quota(t, units=1)
        assert exc.value.code == "QUOTA_EXCEEDED"
