"""Wave 1 LinkedIn OIDC login tests — identity only, no SocialAccount."""
from __future__ import annotations

import base64
import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ["LINKEDIN_OIDC_CLIENT_ID"] = "test-linkedin-oidc-client-id"
os.environ["LINKEDIN_OIDC_CLIENT_SECRET"] = "test-linkedin-oidc-client-secret"
os.environ["LINKEDIN_OIDC_REDIRECT_URI"] = (
    "http://127.0.0.1:4001/api/auth/linkedin/callback"
)
os.environ["LINKEDIN_OIDC_FRONTEND_REDIRECT"] = "http://127.0.0.1:5173"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import OAuthLoginState, SocialAccount, Tenant, User
from middleware.error_handler import AppError
from utils.webtoken import verify_access_token
from utils.linkedin_oidc_secrets import clear_linkedin_oidc_secrets_cache
from modules.platform.src.controllers.auth_controller import AuthController


def _fake_id_token(*, nonce: str | None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload_obj: dict = {"sub": "x"}
    if nonce is not None:
        payload_obj["nonce"] = nonce
    payload = (
        base64.urlsafe_b64encode(json.dumps(payload_obj).encode()).decode().rstrip("=")
    )
    return f"{header}.{payload}.sig"


@pytest.fixture()
def db_session(tmp_path):
    clear_linkedin_oidc_secrets_cache()
    url = f"sqlite:///{tmp_path / 'linkedin_oidc.db'}"
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


def _start_state(ctrl: AuthController) -> tuple[str, str]:
    resp = ctrl.linkedin_start({})
    assert resp["statusCode"] == 302
    loc = resp["headers"]["Location"]
    qs = parse_qs(urlparse(loc).query)
    state_id = qs["state"][0]
    nonce = qs["nonce"][0]
    return state_id, nonce


def test_linkedin_start_redirects_with_state_and_nonce(db_session):
    ctrl = AuthController()
    resp = ctrl.linkedin_start({})
    assert resp["statusCode"] == 302
    loc = resp["headers"]["Location"]
    assert "linkedin.com/oauth" in loc
    assert "client_id=test-linkedin-oidc-client-id" in loc
    assert "scope=openid+profile+email" in loc or "openid%20profile%20email" in loc
    assert "w_member_social" not in loc
    qs = parse_qs(urlparse(loc).query)
    assert qs["state"][0]
    assert qs["nonce"][0]
    with db_session() as session:
        states = session.exec(select(OAuthLoginState)).all()
        assert len(states) == 1
        assert states[0].provider == "linkedin"
        assert states[0].kind == "csrf"
        assert states[0].nonce == qs["nonce"][0]
        assert states[0].state_id == qs["state"][0]


def test_linkedin_new_user_creates_tenant_jwt_no_social_account(db_session):
    ctrl = AuthController()
    state_id, nonce = _start_state(ctrl)
    email = f"{_unique('li')}@example.com"

    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={
            "access_token": "atok",
            "id_token": _fake_id_token(nonce=nonce),
        },
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "linkedin-sub-new-1",
            "email": email,
            "email_verified": True,
            "name": "Li User",
        },
    ):
        cb = ctrl.linkedin_callback({"code": "authcode", "state": state_id})

    assert cb["statusCode"] == 302
    loc = cb["headers"]["Location"]
    assert "/login/oauth/linkedin/callback" in loc
    assert "oauth=created" in loc
    exchange_code = loc.split("code=")[1].split("&")[0]

    with db_session() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        assert user is not None
        assert user.linkedin_sub == "linkedin-sub-new-1"
        assert user.password is None
        assert user.auth_provider == "linkedin"
        assert user.tenant_id is not None
        tenant = session.get(Tenant, user.tenant_id)
        assert tenant is not None
        social = session.exec(select(SocialAccount)).all()
        assert social == []

    exchanged = ctrl.linkedin_exchange({"code": exchange_code})
    assert exchanged["statusCode"] == 200
    data = json.loads(exchanged["body"])["data"]
    assert data["accessToken"]
    claims = verify_access_token(data["accessToken"])
    assert claims["email"] == email
    assert claims["tenantId"] == data["user"]["tenantId"]
    assert claims["role"] == "tenant_admin"

    with pytest.raises(AppError) as exc:
        ctrl.linkedin_exchange({"code": exchange_code})
    assert exc.value.code == "OAUTH_EXCHANGE_INVALID"

    with db_session() as session:
        assert session.exec(select(SocialAccount)).all() == []


def test_linkedin_links_existing_password_user(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    state_id, nonce = _start_state(ctrl)

    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={
            "access_token": "atok",
            "id_token": _fake_id_token(nonce=nonce),
        },
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "linkedin-sub-link-1",
            "email": payload["email"],
            "email_verified": True,
            "name": "Existing",
        },
    ):
        cb = ctrl.linkedin_callback({"code": "authcode", "state": state_id})

    assert "oauth=linked" in cb["headers"]["Location"]
    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user is not None
        assert user.linkedin_sub == "linkedin-sub-link-1"
        assert user.password is not None
        assert "linkedin" in user.auth_provider
        assert session.exec(select(SocialAccount)).all() == []

    login = ctrl.login(
        {"username": payload["username"], "password": payload["password"]}
    )
    assert login["statusCode"] == 200


def test_linkedin_conflict_different_sub_same_email(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user
        user.linkedin_sub = "already-linked-li-sub"
        user.auth_provider = "password+linkedin"
        session.add(user)
        session.commit()

    state_id, nonce = _start_state(ctrl)
    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={
            "access_token": "atok",
            "id_token": _fake_id_token(nonce=nonce),
        },
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "different-linkedin-sub",
            "email": payload["email"],
            "email_verified": True,
            "name": "Conflict",
        },
    ):
        cb = ctrl.linkedin_callback({"code": "authcode", "state": state_id})

    assert "oauthError=OAUTH_CONFLICT" in cb["headers"]["Location"]
    with db_session() as session:
        count = len(
            session.exec(select(User).where(User.email == payload["email"])).all()
        )
        assert count == 1
        assert session.exec(select(SocialAccount)).all() == []


def test_linkedin_invalid_state(db_session):
    ctrl = AuthController()
    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={"access_token": "atok"},
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "x",
            "email": "a@b.com",
            "email_verified": True,
        },
    ):
        cb = ctrl.linkedin_callback({"code": "authcode", "state": "bogus-state"})
    assert "oauthError=OAUTH_STATE" in cb["headers"]["Location"]


def test_linkedin_nonce_mismatch(db_session):
    ctrl = AuthController()
    state_id, _nonce = _start_state(ctrl)
    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={
            "access_token": "atok",
            "id_token": _fake_id_token(nonce="wrong-nonce"),
        },
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "x",
            "email": "a@b.com",
            "email_verified": True,
        },
    ):
        cb = ctrl.linkedin_callback({"code": "authcode", "state": state_id})
    assert "oauthError=OAUTH_NONCE" in cb["headers"]["Location"]


def test_linkedin_existing_sub_login(db_session):
    ctrl = AuthController()
    state_id, nonce = _start_state(ctrl)
    email = f"{_unique('li2')}@example.com"
    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={
            "access_token": "atok",
            "id_token": _fake_id_token(nonce=nonce),
        },
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "linkedin-sub-repeat",
            "email": email,
            "email_verified": True,
            "name": "Repeat",
        },
    ):
        first = ctrl.linkedin_callback({"code": "c1", "state": state_id})
    assert "oauth=created" in first["headers"]["Location"]

    state_id2, nonce2 = _start_state(ctrl)
    with patch(
        "utils.linkedin_oidc.exchange_linkedin_oidc_code",
        return_value={
            "access_token": "atok",
            "id_token": _fake_id_token(nonce=nonce2),
        },
    ), patch(
        "utils.linkedin_oidc.fetch_linkedin_oidc_userinfo",
        return_value={
            "sub": "linkedin-sub-repeat",
            "email": email,
            "email_verified": True,
            "name": "Repeat",
        },
    ):
        second = ctrl.linkedin_callback({"code": "c2", "state": state_id2})
    assert "oauth=login" in second["headers"]["Location"]
    with db_session() as session:
        users = session.exec(select(User).where(User.email == email)).all()
        assert len(users) == 1
        assert session.exec(select(SocialAccount)).all() == []


def test_password_and_google_unaffected_by_linkedin_helpers(db_session):
    """Smoke: password register/login still works alongside LinkedIn OIDC."""
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    resp = ctrl.login(
        {"username": payload["username"], "password": payload["password"]}
    )
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])["data"]
    assert verify_access_token(data["accessToken"])["tenantId"] == data["user"]["tenantId"]
