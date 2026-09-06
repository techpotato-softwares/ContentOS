"""First-run onboarding state and completion tests."""
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
from database.models import ContentPost, Role, SocialAccount, Tenant, User
from middleware.error_handler import ValidationError
from utils.onboarding import (
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    default_onboarding,
    get_or_init_onboarding,
    mark_onboarding_step,
    public_onboarding,
    skip_onboarding,
    verify_step_complete,
)
from modules.tenants.src.controllers.tenants_controller import TenantsController


def _unique(prefix: str = "t") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def db_ctx(tmp_path):
    url = f"sqlite:///{tmp_path / 'onboarding.db'}"
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

    with _get_session() as s:
        tenant = Tenant(
            name="Acme",
            slug=_unique("acme"),
            onboarding_json=json.dumps(default_onboarding()),
        )
        s.add(tenant)
        s.flush()
        role = Role(role_name=_unique("role"), description="t")
        s.add(role)
        s.flush()
        user = User(
            username=_unique("u"),
            email=f"{_unique('e')}@example.com",
            password="x",
            role_id=role.role_id,
            tenant_id=tenant.tenant_id,
        )
        s.add(user)
        s.commit()
        s.refresh(tenant)
        s.refresh(user)
        tid = tenant.tenant_id
        uid = user.user_id

    with patch.object(db_mod, "get_session", _get_session), patch.object(
        db_mod, "get_engine", lambda: engine
    ), patch(
        "modules.tenants.src.controllers.tenants_controller.get_session", _get_session
    ):
        yield {"factory": factory, "tenant_id": tid, "user_id": uid}

    db_mod._engine = None
    db_mod._SessionLocal = None


def _admin(tid: int) -> dict:
    return {
        "userId": 1,
        "tenantId": tid,
        "role": "tenant_admin",
        "permissions": ["tenant:admin", "agent:chat", "training:manage", "posts:publish"],
        "modulesEnabled": ["platform", "tenants", "agent", "publishing"],
    }


def test_default_onboarding_pending():
    state = default_onboarding()
    assert state["status"] == STATUS_PENDING
    assert state["steps"]["linkedin"] is False
    pub = public_onboarding(state)
    assert pub["visible"] is True


def test_get_onboarding_api(db_ctx):
    ctrl = TenantsController()
    resp = ctrl.get_onboarding(user=_admin(db_ctx["tenant_id"]))
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])["data"]
    assert data["status"] == "pending"
    assert data["visible"] is True
    assert data["steps"]["publish"] is False


def test_skip_persists_and_hides(db_ctx):
    ctrl = TenantsController()
    resp = ctrl.skip_onboarding_endpoint(user=_admin(db_ctx["tenant_id"]))
    data = json.loads(resp["body"])["data"]
    assert data["status"] == STATUS_SKIPPED
    assert data["visible"] is False
    assert data["skippedAt"]

    again = ctrl.get_onboarding(user=_admin(db_ctx["tenant_id"]))
    data2 = json.loads(again["body"])["data"]
    assert data2["status"] == STATUS_SKIPPED
    assert data2["visible"] is False


def test_mark_training_step(db_ctx):
    with db_ctx["factory"]() as session:
        state = mark_onboarding_step(
            session, tenant_id=db_ctx["tenant_id"], step="training"
        )
        session.commit()
        assert state["steps"]["training"] is True
        assert state["status"] == STATUS_PENDING


def test_publish_step_auto_completes_wizard(db_ctx):
    with db_ctx["factory"]() as session:
        mark_onboarding_step(session, tenant_id=db_ctx["tenant_id"], step="linkedin")
        mark_onboarding_step(session, tenant_id=db_ctx["tenant_id"], step="training")
        mark_onboarding_step(session, tenant_id=db_ctx["tenant_id"], step="generate")
        state = mark_onboarding_step(
            session, tenant_id=db_ctx["tenant_id"], step="publish"
        )
        session.commit()
        assert state["steps"]["publish"] is True
        assert state["status"] == STATUS_COMPLETED
        assert state["completedAt"]
        assert public_onboarding(state)["visible"] is False


def test_complete_step_requires_backend_facts(db_ctx):
    ctrl = TenantsController()
    with pytest.raises(ValidationError):
        ctrl.complete_onboarding_step("linkedin", user=_admin(db_ctx["tenant_id"]))

    with db_ctx["factory"]() as session:
        session.add(
            SocialAccount(
                tenant_id=db_ctx["tenant_id"],
                platform="linkedin",
                account_kind="member",
                author_urn="urn:li:person:1",
                is_active=True,
            )
        )
        session.commit()

    resp = ctrl.complete_onboarding_step("linkedin", user=_admin(db_ctx["tenant_id"]))
    data = json.loads(resp["body"])["data"]
    assert data["steps"]["linkedin"] is True


def test_legacy_tenant_with_published_post_auto_completes(db_ctx):
    with db_ctx["factory"]() as session:
        t = session.get(Tenant, db_ctx["tenant_id"])
        t.onboarding_json = "{}"
        session.add(
            ContentPost(
                tenant_id=db_ctx["tenant_id"],
                user_id=db_ctx["user_id"],
                angle="educational",
                caption="Hello",
                image_prompt="n/a",
                status="published",
            )
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        state = get_or_init_onboarding(session, t)
        session.commit()
        assert state["status"] == STATUS_COMPLETED
        assert all(state["steps"].values())


def test_verify_generate_and_publish_facts(db_ctx):
    with db_ctx["factory"]() as session:
        t = session.get(Tenant, db_ctx["tenant_id"])
        assert verify_step_complete(session, t, "generate") is False
        session.add(
            ContentPost(
                tenant_id=db_ctx["tenant_id"],
                user_id=db_ctx["user_id"],
                angle="educational",
                caption="Draft",
                image_prompt="n/a",
                status="draft",
            )
        )
        session.commit()
        session.refresh(t)
        assert verify_step_complete(session, t, "generate") is True
        assert verify_step_complete(session, t, "publish") is False
