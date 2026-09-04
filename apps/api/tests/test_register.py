"""Integration tests for production self-serve signup (POST /api/register).

Seed scripts are NOT used — registration must bootstrap RBAC and create
Tenant + User + tenant_admin membership atomically.
"""
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
from database.models import User, Tenant, Role
from middleware.error_handler import ConflictError, ValidationError, AppError
from utils.webtoken import verify_access_token
from modules.platform.src.controllers.auth_controller import AuthController


@pytest.fixture()
def db_session(tmp_path):
    """Isolated SQLite DB per test; patches get_session / get_engine."""
    url = f"sqlite:///{tmp_path / 'register.db'}"
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
        "modules.platform.src.controllers.auth_controller.get_session", _get_session
    ):
        yield factory

    db_mod._engine = None
    db_mod._SessionLocal = None


def _unique(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _register(ctrl: AuthController, **overrides):
    base = {
        "username": _unique("user"),
        "email": f"{_unique('mail')}@example.com",
        "password": "SecurePass123!",
        "companyName": f"Acme {_unique('co')}",
    }
    base.update(overrides)
    return base, ctrl.register(base)


def test_register_creates_user_tenant_and_tenant_admin(db_session):
    ctrl = AuthController()
    payload, resp = _register(ctrl)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["success"] is True
    data = body["data"]
    assert data["user"]["email"] == payload["email"]
    assert data["user"]["roleName"] == "tenant_admin"
    assert data["user"]["tenantId"] is not None
    assert data["tenant"]["name"] == payload["companyName"]
    assert data["accessToken"]

    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user is not None
        assert user.tenant_id == data["user"]["tenantId"]
        tenant = session.get(Tenant, user.tenant_id)
        assert tenant is not None
        assert tenant.name == payload["companyName"]
        role = session.get(Role, user.role_id)
        assert role is not None
        assert role.role_name == "tenant_admin"


def test_register_jwt_contains_tenant_and_role(db_session):
    ctrl = AuthController()
    _, resp = _register(ctrl)
    data = json.loads(resp["body"])["data"]
    claims = verify_access_token(data["accessToken"])
    assert claims.get("tenantId") == data["user"]["tenantId"]
    assert claims.get("role") == "tenant_admin"
    assert claims.get("userId") == data["user"]["userId"]


def test_login_after_register(db_session):
    ctrl = AuthController()
    payload, reg = _register(ctrl)
    login_resp = ctrl.login(
        {"username": payload["email"], "password": payload["password"]}
    )
    assert login_resp["statusCode"] == 200
    login_data = json.loads(login_resp["body"])["data"]
    claims = verify_access_token(login_data["accessToken"])
    assert claims.get("tenantId") is not None
    assert claims.get("role") == "tenant_admin"


def test_authenticated_agent_sessions_after_register(db_session):
    """Registered JWT can call an authenticated agent endpoint."""
    ctrl = AuthController()
    _, reg = _register(ctrl)
    data = json.loads(reg["body"])["data"]
    claims = verify_access_token(data["accessToken"])
    assert claims.get("tenantId")
    assert claims.get("role") == "tenant_admin"

    from modules.agent.src.controllers.agent_controller import AgentController

    agent = AgentController()
    with patch(
        "modules.agent.src.controllers.agent_controller.get_session",
        db_session,
    ):
        resp = agent.list_sessions(user=claims)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_duplicate_email_returns_409(db_session):
    ctrl = AuthController()
    email = f"{_unique('dup')}@example.com"
    _register(ctrl, email=email, username=_unique("a"))
    with pytest.raises(ConflictError) as exc:
        _register(ctrl, email=email, username=_unique("b"), companyName="Other Co")
    assert exc.value.status_code == 409
    assert "email" in exc.value.message.lower()
    # Envelope path via error handler should also be clean JSON
    from middleware.error_handler import create_error_response

    resp = create_error_response(exc.value)
    assert resp["statusCode"] == 409
    err = json.loads(resp["body"])["error"]
    assert err["code"] == "CONFLICT"
    assert "Traceback" not in err["message"]


def test_missing_company_name_validation(db_session):
    ctrl = AuthController()
    with pytest.raises(ValidationError) as exc:
        ctrl.register(
            {
                "username": _unique("x"),
                "email": f"{_unique('x')}@example.com",
                "password": "SecurePass123!",
            }
        )
    assert exc.value.status_code == 400
    assert "companyName" in exc.value.message


def test_registration_failure_rolls_back_no_orphans(db_session):
    """If user creation fails after tenant flush, nothing is committed."""
    ctrl = AuthController()
    email = f"{_unique('fail')}@example.com"
    username = _unique("failuser")
    company = f"Fail Co {_unique('c')}"

    with patch(
        "modules.platform.src.controllers.auth_controller.bcrypt.hash",
        side_effect=RuntimeError("simulated user create failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated"):
            ctrl.register(
                {
                    "username": username,
                    "email": email,
                    "password": "SecurePass123!",
                    "companyName": company,
                }
            )

    with db_session() as session:
        assert session.exec(select(User).where(User.email == email)).first() is None
        assert session.exec(select(User).where(User.username == username)).first() is None
        assert session.exec(select(Tenant).where(Tenant.name == company)).first() is None


def test_slug_collision_derives_unique_slug(db_session):
    ctrl = AuthController()
    company = "Same Name Co"
    _, first = _register(ctrl, companyName=company, username=_unique("s1"))
    _, second = _register(ctrl, companyName=company, username=_unique("s2"))
    slug1 = json.loads(first["body"])["data"]["tenant"]["slug"]
    slug2 = json.loads(second["body"])["data"]["tenant"]["slug"]
    assert slug1 != slug2
