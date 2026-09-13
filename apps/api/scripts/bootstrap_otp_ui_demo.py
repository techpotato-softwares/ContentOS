"""Bootstrap SQLite DB + demo user for local OTP UI demo (no Docker)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

DB = ROOT / "media" / "otp_ui_demo.db"
DB.parent.mkdir(exist_ok=True)
if DB.exists():
    DB.unlink()

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["JWT_SECRET"] = "demo-jwt-secret-at-least-32-characters-xx"
os.environ["JWT_REFRESH_SECRET"] = "demo-refresh-secret-at-least-32-chars-x"
os.environ["SES_ENABLED"] = "false"
os.environ["SES_FROM_EMAIL"] = "noreply@contentos.local"
os.environ["OTP_RATE_LIMIT_PER_EMAIL"] = "20"

from database import init_db, get_session  # noqa: E402
from modules.platform.src.controllers.auth_controller import AuthController  # noqa: E402

init_db()
ctrl = AuthController()
resp = ctrl.register(
    {
        "username": "otpdemo",
        "email": "otp.demo@contentos.local",
        "password": "SecurePass123!",
        "companyName": "OTP Demo Co",
    }
)
print("register", resp["statusCode"], DB)
print("Use email: otp.demo@contentos.local")
print("DATABASE_URL=", os.environ["DATABASE_URL"])
