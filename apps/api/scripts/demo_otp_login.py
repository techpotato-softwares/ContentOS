"""Live OTP login demo (SQLite, no Docker). Prints email payload + JWT session."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "demo-jwt-secret-at-least-32-characters-xx"
os.environ["JWT_REFRESH_SECRET"] = "demo-refresh-secret-at-least-32-chars-x"
os.environ["SES_ENABLED"] = "false"
os.environ["SES_FROM_EMAIL"] = "noreply@contentos.local"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel

import database as db_mod
from modules.platform.src.controllers.auth_controller import AuthController

DEMO_CODE = "482913"
EMAIL = "otp.demo@contentos.local"
PASSWORD = "SecurePass123!"


def main() -> None:
    db_path = Path(tempfile.gettempdir()) / "contentos_otp_demo.db"
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    SQLModel.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, class_=Session
    )
    db_mod._engine = engine
    db_mod._SessionLocal = factory

    def _get_session():
        return factory()

    captured: dict = {}

    def _capture_send(*, to_email: str, code: str, expires_minutes: int):
        captured["to"] = to_email
        captured["code"] = code
        captured["expires_minutes"] = expires_minutes
        print("\n========== OTP EMAIL (SES preview) ==========")
        print(f"To:      {to_email}")
        print(f"Subject: Your ContentOS sign-in code")
        print(f"Body:    Your ContentOS sign-in code is: {code}")
        print(f"Expires: {expires_minutes} minutes")
        print("=============================================\n")
        return {"sent": False, "reason": "ses_disabled", "preview": True}

    with patch.object(db_mod, "get_session", _get_session), patch(
        "modules.platform.src.controllers.auth_controller.get_session", _get_session
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.generate_otp_code",
        return_value=DEMO_CODE,
    ), patch(
        "modules.platform.src.controllers.auth_controller.otp_util.send_login_otp_email",
        side_effect=_capture_send,
    ):
        ctrl = AuthController()

        print("1) Register company user…")
        reg = ctrl.register(
            {
                "username": "otpdemo",
                "email": EMAIL,
                "password": PASSWORD,
                "companyName": "OTP Demo Co",
            }
        )
        assert reg["statusCode"] == 201, reg
        print("   OK — user + tenant created")

        print("2) Request OTP…")
        req = ctrl.request_otp({"email": EMAIL})
        assert req["statusCode"] == 200, req
        req_body = json.loads(req["body"])["data"]
        print(f"   API: {req_body.get('message')}")
        print(f"   expiresIn: {req_body.get('expiresIn')}s")
        assert captured.get("code") == DEMO_CODE

        print("3) Verify OTP -> JWT session...")
        verify = ctrl.verify_otp({"email": EMAIL, "code": DEMO_CODE})
        assert verify["statusCode"] == 200, verify.loads(verify["body"])
        data = json.loads(verify["body"])["data"]
        user = data["user"]
        print("   Login successful")
        print(f"   user: {user['username']} <{user['email']}>")
        print(f"   role: {user['roleName']}  tenantId: {user['tenantId']}")
        print(f"   accessToken: {data['accessToken'][:48]}…")
        print("\nDone — same JWT + tenant session as password login.")


if __name__ == "__main__":
    main()
