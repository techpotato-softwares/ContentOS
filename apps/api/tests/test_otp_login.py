"""Wave 1 passwordless email OTP login tests."""
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
os.environ["OTP_TTL_SECONDS"] = "600"
os.environ["OTP_MAX_ATTEMPTS"] = "5"
os.environ["OTP_RATE_LIMIT_PER_EMAIL"] = "3"
os.environ["OTP_RATE_WINDOW_SECONDS"] = "900"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import EmailOtpChallenge, User
from middleware.error_handler import AppError, ValidationError
from utils.webtoken import verify_access_token
from utils import email_otp as otp_util
from modules.platform.src.controllers.auth_controller import AuthController


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'otp.db'}"
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


def _body(resp: dict) -> dict:
    return json.loads(resp["body"])


def test_otp_login_success_issues_same_jwt_tenant_session(db_session):
    ctrl = AuthController()
    payload, reg = _register(ctrl)
    assert reg["statusCode"] == 201
    reg_data = _body(reg)["data"]

    with patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value="123456",
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        return_value={"sent": True, "reason": "ses_disabled"},
    ) as send_mock:
        req = ctrl.request_otp({"email": payload["email"]})
        assert req["statusCode"] == 200
        send_mock.assert_called_once()
        assert send_mock.call_args.kwargs["to_email"] == payload["email"].lower()
        # Never pass unexpected logging of code elsewhere — call includes code once for email
        assert send_mock.call_args.kwargs["code"] == "123456"

    verify = ctrl.verify_otp({"email": payload["email"], "code": "123456"})
    assert verify["statusCode"] == 200
    data = _body(verify)["data"]
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["user"]["email"] == payload["email"].lower()
    assert data["user"]["tenantId"] == reg_data["user"]["tenantId"]
    assert data["user"]["roleName"] == "tenant_admin"

    claims = verify_access_token(data["accessToken"])
    assert claims["tenantId"] == reg_data["user"]["tenantId"]
    assert claims["role"] == "tenant_admin"
    assert claims["userId"] == reg_data["user"]["userId"]
    assert claims["email"] == payload["email"].lower()

    # Challenge consumed
    with db_session() as session:
        rows = session.exec(
            select(EmailOtpChallenge).where(
                EmailOtpChallenge.email == payload["email"].lower()
            )
        ).all()
        assert all(r.consumed_at is not None for r in rows) or len(rows) == 0


def test_otp_invalid_code(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    with patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value="654321",
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        return_value={"sent": True, "reason": "ses_disabled"},
    ):
        ctrl.request_otp({"email": payload["email"]})

    with pytest.raises(AppError) as exc:
        ctrl.verify_otp({"email": payload["email"], "code": "000000"})
    assert exc.value.status_code == 401
    assert exc.value.code == "OTP_INVALID"


def test_otp_expired(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    with patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value="111222",
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        return_value={"sent": True, "reason": "ses_disabled"},
    ):
        ctrl.request_otp({"email": payload["email"]})

    with db_session() as session:
        row = session.exec(
            select(EmailOtpChallenge).where(
                EmailOtpChallenge.email == payload["email"].lower()
            )
        ).first()
        assert row is not None
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        session.add(row)
        session.commit()

    with pytest.raises(AppError) as exc:
        ctrl.verify_otp({"email": payload["email"], "code": "111222"})
    assert exc.value.status_code == 400
    assert exc.value.code == "OTP_EXPIRED"


def test_otp_reuse_prevented(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    with patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value="777888",
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        return_value={"sent": True, "reason": "ses_disabled"},
    ):
        ctrl.request_otp({"email": payload["email"]})

    first = ctrl.verify_otp({"email": payload["email"], "code": "777888"})
    assert first["statusCode"] == 200

    with pytest.raises(AppError) as exc:
        ctrl.verify_otp({"email": payload["email"], "code": "777888"})
    assert exc.value.code in ("OTP_NOT_FOUND", "OTP_INVALID", "OTP_EXPIRED")


def test_otp_rate_limiting(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    with patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value="101010",
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        return_value={"sent": True, "reason": "ses_disabled"},
    ):
        for _ in range(3):
            resp = ctrl.request_otp({"email": payload["email"]})
            assert resp["statusCode"] == 200
        with pytest.raises(AppError) as exc:
            ctrl.request_otp({"email": payload["email"]})
        assert exc.value.status_code == 429
        assert exc.value.code == "RATE_LIMITED"


def test_otp_request_unknown_email(db_session):
    ctrl = AuthController()
    with pytest.raises(AppError) as exc:
        ctrl.request_otp({"email": "nobody@example.com"})
    assert exc.value.status_code == 404


def test_otp_request_invalid_email(db_session):
    ctrl = AuthController()
    with pytest.raises(ValidationError):
        ctrl.request_otp({"email": "not-an-email"})


def test_otp_stored_hashed_not_plaintext(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    code = "424242"
    with patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value=code,
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        return_value={"sent": True, "reason": "ses_disabled"},
    ):
        ctrl.request_otp({"email": payload["email"]})

    with db_session() as session:
        row = session.exec(
            select(EmailOtpChallenge).where(
                EmailOtpChallenge.email == payload["email"].lower()
            )
        ).first()
        assert row is not None
        assert row.code_hash != code
        assert code not in row.code_hash
        assert otp_util.verify_otp_hash(
            code, email=payload["email"], code_hash=row.code_hash
        )


def test_password_login_still_works(db_session):
    ctrl = AuthController()
    payload, _ = _register(ctrl)
    resp = ctrl.login(
        {"username": payload["username"], "password": payload["password"]}
    )
    assert resp["statusCode"] == 200
    data = _body(resp)["data"]
    assert data["accessToken"]
    claims = verify_access_token(data["accessToken"])
    assert claims["tenantId"] == data["user"]["tenantId"]
