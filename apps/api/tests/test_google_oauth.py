"""Wave 1 Google OAuth login tests."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta
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
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://127.0.0.1:4001/api/auth/google/callback"
os.environ["GOOGLE_FRONTEND_REDIRECT"] = "http://127.0.0.1:5173"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import OAuthLoginState, Tenant, User
from middleware.error_handler import AppError, ConflictError
from utils.webtoken import verify_access_token
from utils.google_oauth_secrets import clear_google_oauth_secrets_cache
from modules.platform.src.controllers.auth_controller import AuthController


@pytest.fixture()
def db_session(tmp_path):
    clear_google_oauth_secrets_cache()
    url = f"sqlite:///{tmp_path / 'google_oauth.db'}"
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


def test_google_start_redirects_with_state(db_session):
    ctrl = AuthController()
    resp = ctrl.google_start({})
    assert resp["statusCode"] == 302
    loc = resp["headers"]["Location"]
    assert "accounts.google.com" in loc
    assert "client_id=test-google-client-id" in loc
    with db_session() as session:
        states = session.exec(select(OAuthLoginState)).all()
        assert len(states) == 1
        assert states[0].kind == "csrf"
        assert states[0].state_id in loc


def test_google_new_user_creates_tenant_and_exchange(db_session):
    ctrl = AuthController()
    start = ctrl.google_start({})
    state_id = start["headers"]["Location"].split("state=")[1].split("&")[0]

    email = f"{_unique('g')}@example.com"
    with patch(
        "utils.google_oauth.exchange_google_code",
        return_value={"access_token": "atok"},
    ), patch(
        "utils.google_oauth.fetch_google_userinfo",
        return_value={
            "sub": "google-sub-new-1",
            "email": email,
            "email_verified": True,
            "name": "New User",
        },
    ):
        cb = ctrl.google_callback({"code": "authcode", "state": state_id})

    assert cb["statusCode"] == 302
    loc = cb["headers"]["Location"]
    assert "/login/oauth/callback" in loc
    assert "oauth=created" in loc
    assert "code=" in loc
    exchange_code = loc.split("code=")[1].split("&")[0]

    with db_session() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        assert user is not None
        assert user.google_sub == "google-sub-new-1"
        assert user.password is None
        assert user.auth_provider == "google"
        assert user.tenant_id is not None
        tenant = session.get(Tenant, user.tenant_id)
        assert tenant is not None

    exchanged = ctrl.google_exchange({"code": exchange_code})
    assert exchanged["statusCode"] == 200
    data = json.loads(exchanged["body"])["data"]
    assert data["accessToken"]
    claims = verify_access_token(data["accessToken"])
    assert claims["email"] == email
    assert claims["tenantId"] == data["user"]["tenantId"]
    assert claims["role"] == "tenant_admin"

    # reuse blocked
    with pytest.raises(AppError) as exc:
        ctrl.google_exchange({"code": exchange_code})
    assert exc.value.code == "OAUTH_EXCHANGE_INVALID"


def test_google_links_existing_password_user(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    start = ctrl.google_start({})
    state_id = start["headers"]["Location"].split("state=")[1].split("&")[0]

    with patch(
        "utils.google_oauth.exchange_google_code",
        return_value={"access_token": "atok"},
    ), patch(
        "utils.google_oauth.fetch_google_userinfo",
        return_value={
            "sub": "google-sub-link-1",
            "email": payload["email"],
            "email_verified": True,
            "name": "Existing",
        },
    ):
        cb = ctrl.google_callback({"code": "authcode", "state": state_id})

    assert "oauth=linked" in cb["headers"]["Location"]
    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user is not None
        assert user.google_sub == "google-sub-link-1"
        assert user.password is not None
        assert "google" in user.auth_provider

    # password login still works
    login = ctrl.login(
        {"username": payload["username"], "password": payload["password"]}
    )
    assert login["statusCode"] == 200


def test_google_conflict_different_sub_same_email(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user
        user.google_sub = "already-linked-sub"
        user.auth_provider = "password+google"
        session.add(user)
        session.commit()

    start = ctrl.google_start({})
    state_id = start["headers"]["Location"].split("state=")[1].split("&")[0]

    with patch(
        "utils.google_oauth.exchange_google_code",
        return_value={"access_token": "atok"},
    ), patch(
        "utils.google_oauth.fetch_google_userinfo",
        return_value={
            "sub": "different-google-sub",
            "email": payload["email"],
            "email_verified": True,
            "name": "Conflict",
        },
    ):
        cb = ctrl.google_callback({"code": "authcode", "state": state_id})

    assert cb["statusCode"] == 302
    loc = cb["headers"]["Location"]
    assert "oauthError=OAUTH_CONFLICT" in loc
    with db_session() as session:
        count = len(session.exec(select(User).where(User.email == payload["email"])).all())
        assert count == 1


def test_google_invalid_state(db_session):
    ctrl = AuthController()
    with patch(
        "utils.google_oauth.exchange_google_code",
        return_value={"access_token": "atok"},
    ), patch(
        "utils.google_oauth.fetch_google_userinfo",
        return_value={
            "sub": "x",
            "email": "a@b.com",
            "email_verified": True,
        },
    ):
        cb = ctrl.google_callback({"code": "authcode", "state": "bogus-state"})
    assert "oauthError=OAUTH_STATE" in cb["headers"]["Location"]


def test_google_token_failure(db_session):
    ctrl = AuthController()
    start = ctrl.google_start({})
    state_id = start["headers"]["Location"].split("state=")[1].split("&")[0]
    with patch(
        "utils.google_oauth.exchange_google_code",
        side_effect=RuntimeError("boom"),
    ):
        cb = ctrl.google_callback({"code": "authcode", "state": state_id})
    assert "oauthError=GOOGLE_TOKEN" in cb["headers"]["Location"]


def test_password_login_unchanged(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    resp = ctrl.login(
        {"username": payload["username"], "password": payload["password"]}
    )
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])["data"]
    assert verify_access_token(data["accessToken"])["tenantId"] == data["user"]["tenantId"]
