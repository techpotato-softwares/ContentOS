"""Email verification, password reset, rate limits, session revoke, publish gate."""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from passlib.hash import bcrypt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ["SES_ENABLED"] = "false"
os.environ["SES_FROM_EMAIL"] = "noreply@localhost"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["AUTH_TOKEN_RATE_LIMIT"] = "3"
os.environ["AUTH_TOKEN_RATE_WINDOW_MINUTES"] = "60"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import (
    AuthToken,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
)
from middleware.auth import auth_middleware
from middleware.error_handler import AppError
from utils.auth_tokens import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    hash_token,
    require_email_verified,
)
from utils.webtoken import verify_access_token
from modules.platform.src.controllers.auth_controller import AuthController


def _seed_rbac(session: Session) -> Role:
    role = Role(role_name="tenant_admin", description="Tenant admin")
    session.add(role)
    session.flush()
    for code in ("agent:chat", "posts:publish", "posts:review", "tenant:admin"):
        perm = Permission(permission_code=code, permission_name=code)
        session.add(perm)
        session.flush()
        session.add(
            RolePermission(role_id=role.role_id, permission_id=perm.permission_id)
        )
    session.commit()
    session.refresh(role)
    return role


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'auth_email.db'}"
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
        _seed_rbac(s)

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
        "companyName": f"Co {_unique('c')}",
    }
    base.update(overrides)
    return base, ctrl.register(base)


def _token_from_dev_link(dev_link: str) -> str:
    m = re.search(r"token=([^&]+)", dev_link or "")
    assert m, f"expected token in {dev_link!r}"
    return m.group(1)


def test_verify_email_confirm_marks_verified(db_session):
    ctrl = AuthController()
    payload, reg = _register(ctrl)
    data = json.loads(reg["body"])["data"]
    raw = _token_from_dev_link(data["devLink"])
    assert "token=" not in json.dumps(reg).split("devLink")[0]  # not elsewhere casually

    confirm = ctrl.verify_email_confirm({"token": raw})
    assert confirm["statusCode"] == 200
    body = json.loads(confirm["body"])["data"]
    assert body["user"]["emailVerified"] is True
    claims = verify_access_token(body["accessToken"])
    assert claims.get("emailVerified") is True

    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user.email_verified_at is not None
        row = session.exec(
            select(AuthToken).where(AuthToken.token_hash == hash_token(raw))
        ).first()
        assert row.used_at is not None


def test_verify_token_reuse_and_invalid(db_session):
    ctrl = AuthController()
    _, reg = _register(ctrl)
    raw = _token_from_dev_link(json.loads(reg["body"])["data"]["devLink"])
    ctrl.verify_email_confirm({"token": raw})
    with pytest.raises(AppError) as used:
        ctrl.verify_email_confirm({"token": raw})
    assert used.value.code == "TOKEN_USED"

    with pytest.raises(AppError) as inv:
        ctrl.verify_email_confirm({"token": "not-a-real-token"})
    assert inv.value.code == "INVALID_TOKEN"


def test_verify_token_expired(db_session):
    ctrl = AuthController()
    _, reg = _register(ctrl)
    raw = _token_from_dev_link(json.loads(reg["body"])["data"]["devLink"])
    with db_session() as session:
        row = session.exec(
            select(AuthToken).where(AuthToken.token_hash == hash_token(raw))
        ).first()
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        session.add(row)
        session.commit()
    with pytest.raises(AppError) as exc:
        ctrl.verify_email_confirm({"token": raw})
    assert exc.value.code == "TOKEN_EXPIRED"


def test_verify_request_enumeration_safe(db_session):
    ctrl = AuthController()
    known = _register(ctrl)[0]["email"]
    r1 = ctrl.verify_email_request({"email": known})
    r2 = ctrl.verify_email_request({"email": f"{_unique('ghost')}@example.com"})
    m1 = json.loads(r1["body"])["data"]["message"]
    m2 = json.loads(r2["body"])["data"]["message"]
    assert m1 == m2
    assert r1["statusCode"] == 200
    assert r2["statusCode"] == 200


def test_password_reset_request_enumeration_safe(db_session):
    ctrl = AuthController()
    known = _register(ctrl)[0]["email"]
    r1 = ctrl.password_reset_request({"email": known})
    r2 = ctrl.password_reset_request({"email": f"{_unique('ghost')}@example.com"})
    assert json.loads(r1["body"])["data"]["message"] == json.loads(r2["body"])["data"][
        "message"
    ]


def test_password_reset_confirm_and_login(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    req = ctrl.password_reset_request({"email": payload["email"]})
    raw = _token_from_dev_link(json.loads(req["body"])["data"]["devLink"])
    new_pw = "NewSecurePass999!"
    conf = ctrl.password_reset_confirm({"token": raw, "password": new_pw})
    assert conf["statusCode"] == 200

    with pytest.raises(AppError):
        ctrl.login({"username": payload["email"], "password": payload["password"]})

    ok = ctrl.login({"username": payload["email"], "password": new_pw})
    assert ok["statusCode"] == 200
    assert json.loads(ok["body"])["data"]["user"]["emailVerified"] is True


def test_password_reset_invalidates_sessions(db_session):
    ctrl = AuthController()
    payload, reg = _register(ctrl)
    old_access = json.loads(reg["body"])["data"]["accessToken"]
    old_refresh = json.loads(reg["body"])["data"]["refreshToken"]

    req = ctrl.password_reset_request({"email": payload["email"]})
    raw = _token_from_dev_link(json.loads(req["body"])["data"]["devLink"])
    ctrl.password_reset_confirm({"token": raw, "password": "AnotherPass123!"})

    event = {
        "headers": {"Authorization": f"Bearer {old_access}"},
    }
    denied = auth_middleware(event)
    assert denied["statusCode"] == 401
    err = json.loads(denied["body"])["error"]
    assert err["code"] == "SESSION_REVOKED"

    with pytest.raises(AppError) as exc:
        ctrl.refresh({"refreshToken": old_refresh})
    assert exc.value.code == "SESSION_REVOKED"


def test_rate_limit_verify_request(db_session):
    ctrl = AuthController()
    email = _register(ctrl)[0]["email"]
    # register already issued one verify token; with limit=3, two more succeed then next is blocked
    with patch("utils.auth_tokens._RATE_LIMIT", 3):
        ctrl.verify_email_request({"email": email})
        ctrl.verify_email_request({"email": email})
        with pytest.raises(AppError) as exc:
            ctrl.verify_email_request({"email": email})
        assert exc.value.code == "RATE_LIMITED"
        assert exc.value.status_code == 429


def test_require_email_verified_blocks_publishing(db_session):
    with db_session() as session:
        role = session.exec(select(Role).where(Role.role_name == "tenant_admin")).first()
        tenant = Tenant(name="T", slug=_unique("slug"))
        session.add(tenant)
        session.flush()
        unverified = User(
            username=_unique("uv"),
            email=f"{_unique('uv')}@example.com",
            password=bcrypt.hash("SecurePass123!"),
            role_id=role.role_id,
            tenant_id=tenant.tenant_id,
            email_verified_at=None,
        )
        verified = User(
            username=_unique("v"),
            email=f"{_unique('v')}@example.com",
            password=bcrypt.hash("SecurePass123!"),
            role_id=role.role_id,
            tenant_id=tenant.tenant_id,
            email_verified_at=datetime.utcnow(),
        )
        session.add(unverified)
        session.add(verified)
        session.commit()
        session.refresh(unverified)
        session.refresh(verified)

        with pytest.raises(AppError) as exc:
            require_email_verified(unverified)
        assert exc.value.code == "EMAIL_UNVERIFIED"
        require_email_verified(verified)  # no raise


def test_hashed_tokens_not_stored_raw(db_session):
    ctrl = AuthController()
    _, reg = _register(ctrl)
    data = json.loads(reg["body"])["data"]
    raw = _token_from_dev_link(data["devLink"])
    digest = hash_token(raw)
    with db_session() as session:
        rows = session.exec(select(AuthToken)).all()
        assert rows
        assert any(r.token_hash == digest and r.purpose == PURPOSE_EMAIL_VERIFY for r in rows)
        for row in rows:
            assert raw not in (row.token_hash or "")
            assert len(row.token_hash) == 64
