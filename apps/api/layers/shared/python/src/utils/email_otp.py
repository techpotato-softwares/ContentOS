"""Email OTP helpers for passwordless login (Wave 1).

OTPs are always stored hashed (HMAC-SHA256 + pepper). Plaintext codes are never
logged. SES delivery uses ``utils.ses_mail.send_email``.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta

from utils.logger import logger
from utils.ses_mail import send_email

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def otp_ttl_seconds() -> int:
    return max(60, int(os.environ.get("OTP_TTL_SECONDS") or "600"))


def otp_max_attempts() -> int:
    return max(1, int(os.environ.get("OTP_MAX_ATTEMPTS") or "5"))


def otp_code_length() -> int:
    return min(8, max(4, int(os.environ.get("OTP_CODE_LENGTH") or "6")))


def otp_email_rate_limit() -> tuple[int, int]:
    """Max requests per email within window seconds."""
    limit = max(1, int(os.environ.get("OTP_RATE_LIMIT_PER_EMAIL") or "3"))
    window = max(60, int(os.environ.get("OTP_RATE_WINDOW_SECONDS") or "900"))
    return limit, window


def otp_ip_rate_limit() -> tuple[int, int]:
    limit = max(1, int(os.environ.get("OTP_RATE_LIMIT_PER_IP") or "10"))
    window = max(60, int(os.environ.get("OTP_RATE_WINDOW_SECONDS") or "900"))
    return limit, window


def _pepper() -> bytes:
    raw = (
        os.environ.get("OTP_PEPPER")
        or os.environ.get("JWT_SECRET")
        or "contentos-otp-dev-pepper-change-me"
    )
    return raw.encode("utf-8")


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email)) and len(email) <= 254


def generate_otp_code(length: int | None = None) -> str:
    n = length if length is not None else otp_code_length()
    # Cryptographically secure numeric OTP (leading zeros allowed)
    upper = 10**n
    return str(secrets.randbelow(upper)).zfill(n)


def hash_otp(code: str, *, email: str) -> str:
    """HMAC-SHA256 of code bound to normalized email (prevents cross-email reuse)."""
    msg = f"{normalize_email(email)}:{code.strip()}".encode("utf-8")
    return hmac.new(_pepper(), msg, hashlib.sha256).hexdigest()


def verify_otp_hash(code: str, *, email: str, code_hash: str) -> bool:
    expected = hash_otp(code, email=email)
    return hmac.compare_digest(expected, code_hash)


def otp_expires_at(now: datetime | None = None) -> datetime:
    base = now or datetime.utcnow()
    return base + timedelta(seconds=otp_ttl_seconds())


def send_login_otp_email(*, to_email: str, code: str, expires_minutes: int) -> dict:
    """Send OTP via SES. Never include the code in log fields."""
    subject = "Your ContentOS sign-in code"
    text_body = (
        f"Your ContentOS sign-in code is: {code}\n\n"
        f"It expires in {expires_minutes} minutes. "
        "If you did not request this, you can ignore this email."
    )
    html_body = (
        "<p>Your ContentOS sign-in code is:</p>"
        f'<p style="font-size:28px;letter-spacing:4px;font-weight:700">{code}</p>'
        f"<p>It expires in {expires_minutes} minutes.</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
    )
    result = send_email(
        to_addresses=[to_email],
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    # Log delivery outcome only — never the OTP value
    logger.info(
        "Login OTP email dispatch",
        {
            "to": to_email,
            "sent": result.get("sent"),
            "reason": result.get("reason"),
            "messageId": result.get("messageId"),
        },
    )
    return result
