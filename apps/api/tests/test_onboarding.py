"""Tenant first-run onboarding: persistence, skip, sync, auto-complete hooks."""
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
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import (
    ContentPost,
    GenerationBatch,
    Role,
    SocialAccount,
    Tenant,
    User,
)
from modules.platform.src.controllers.auth_controller import _ensure_platform_rbac
from modules.tenants.src.controllers.tenants_controller import TenantsController
# pyrefly: ignore [missing-module-attribute]
from passlib.hash import bcrypt
from utils.onboarding import (
    apply_put_patch,
    complete_onboarding_step,
    default_onboarding_state,
    is_step_complete,
    mark_step_complete,
    parse_onboarding,
    should_show_wizard,
    sync_onboarding_from_reality,
)


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'onboarding.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    # pyrefly: ignore [bad-assignment]
    db_mod._engine = engine
    # pyrefly: ignore [bad-assignment]
    db_mod._SessionLocal = factory

    def _get_session():
        return factory()

    with patch.object(db_mod, "get_session", _get_session), patch.object(
        db_mod, "get_engine", lambda: engine
    ), patch(
        "modules.tenants.src.controllers.tenants_controller.get_session", _get_session
    ):
        yield factory

    db_mod._engine = None
    db_mod._SessionLocal = None


def _seed(session) -> tuple[Tenant, User, dict]:
    admin_role = _ensure_platform_rbac(session)
    assert session.exec(select(Role).where(Role.role_name == "tenant_admin")).first()
    tenant = Tenant(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    user = User(
        username=f"admin_{uuid.uuid4().hex[:6]}",
        email=f"admin_{uuid.uuid4().hex[:6]}@ex.com",
        password=bcrypt.hash("ChangeMe123!"),
        role_id=admin_role.role_id,
        tenant_id=tenant.tenant_id,
    )
    session.add(user)
    session.commit()
    session.refresh(tenant)
    session.refresh(user)
    jwt_user = {
        "userId": user.user_id,
        "username": user.username,
        "email": user.email,
        "tenantId": tenant.tenant_id,
        "role": "tenant_admin",
        "permissions": ["tenant:admin", "training:manage", "agent:chat"],
        "modulesEnabled": ["platform", "tenants", "agent", "publishing"],
    }
    return tenant, user, jwt_user


def _body(resp: dict) -> dict:
    return json.loads(resp["body"])


def test_default_state_shows_wizard():
    state = default_onboarding_state()
    assert should_show_wizard(state) is True
    assert state["skipped"] is False
    assert all(not is_step_complete(state, k) for k in state["steps"])


def test_skip_hides_wizard_permanently():
    state = apply_put_patch(default_onboarding_state(), {"skipped": True})
    assert state["skipped"] is True
    assert state["completedAt"]
    assert should_show_wizard(state) is False


def test_publish_completes_onboarding():
    state = default_onboarding_state()
    for key in ("linkedin", "training", "generate", "review"):
        state = mark_step_complete(state, key)
    state = mark_step_complete(state, "publish")
    assert state["completedAt"]
    assert should_show_wizard(state) is False


def test_get_put_onboarding_persists(db_session):
    with db_session() as session:
        tenant, _user, jwt_user = _seed(session)
        tid = tenant.tenant_id

    ctrl = TenantsController()
    got = _body(ctrl.get_onboarding(user=jwt_user))["data"]
    assert got["showWizard"] is True
    assert got["steps"]["linkedin"]["status"] == "pending"

    skipped = _body(ctrl.put_onboarding({"skipped": True}, user=jwt_user))["data"]
    assert skipped["skipped"] is True
    assert skipped["showWizard"] is False

    # Survives "refresh" (new GET)
    again = _body(ctrl.get_onboarding(user=jwt_user))["data"]
    assert again["skipped"] is True
    assert again["showWizard"] is False

    with db_session() as session:
        row = session.get(Tenant, tid)
        assert row is not None
        stored = parse_onboarding(row.onboarding_json)
        assert stored["skipped"] is True


def test_sync_from_existing_linkedin_and_publish(db_session):
    with db_session() as session:
        tenant, user, jwt_user = _seed(session)
        assert tenant.tenant_id is not None
        assert user.user_id is not None
        session.add(
            SocialAccount(
                tenant_id=tenant.tenant_id,
                platform="linkedin",
                account_kind="member",
                author_urn="urn:li:person:abc",
                is_active=True,
            )
        )
        session.add(
            ContentPost(
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                angle="educational",
                caption="Hello",
                image_prompt="",
                status="published",
            )
        )
        session.commit()

    ctrl = TenantsController()
    data = _body(ctrl.get_onboarding(user=jwt_user))["data"]
    assert data["steps"]["linkedin"]["status"] == "completed"
    assert data["steps"]["publish"]["status"] == "completed"
    assert data["steps"]["review"]["status"] == "completed"
    assert data["showWizard"] is False
    assert data["completedAt"]


def test_complete_onboarding_step_helper(db_session):
    with db_session() as session:
        tenant, user, _jwt = _seed(session)
        assert tenant.tenant_id is not None
        assert user.user_id is not None
        complete_onboarding_step(session, tenant.tenant_id, "generate")
        session.add(
            GenerationBatch(
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                user_brief="brief",
                status="completed",
            )
        )
        session.commit()
        session.refresh(tenant)
        state = sync_onboarding_from_reality(session, tenant)
        session.commit()
        assert state["steps"]["generate"]["status"] == "completed"


def test_put_training_marks_training_step(db_session):
    with db_session() as session:
        _tenant, _user, jwt_user = _seed(session)

    ctrl = TenantsController()
    from training.schema import TenantTrainingSchema

    training = TenantTrainingSchema.model_validate(
        {"company": {"display_name": "Acme Co", "industry": "Software"}}
    )
    resp = ctrl.put_training(data=training.model_dump(), user=jwt_user)
    assert _body(resp).get("success") is True

    onboarding = _body(ctrl.get_onboarding(user=jwt_user))["data"]
    assert onboarding["steps"]["training"]["status"] == "completed"


def test_reopen_after_skip(db_session):
    with db_session() as session:
        _tenant, _user, jwt_user = _seed(session)
    ctrl = TenantsController()
    ctrl.put_onboarding({"skipped": True}, user=jwt_user)
    reopened = _body(
        ctrl.put_onboarding({"skipped": False, "reopen": True}, user=jwt_user)
    )["data"]
    assert reopened["skipped"] is False
    assert reopened["showWizard"] is True
