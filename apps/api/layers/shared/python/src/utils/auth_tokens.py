"""One-time auth tokens: email verification + password reset (hashed at rest)."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Literal

from sqlmodel import select

from database.models import AuthToken, User
from middleware.error_handler import AppError, ValidationError

Purpose = Literal["email_verify", "password_reset"]

PURPOSE_EMAIL_VERIFY = "email_verify"
PURPOSE_PASSWORD_RESET = "password_reset"

_TTL_MINUTES = {
    PURPOSE_EMAIL_VERIFY: int(os.environ.get("EMAIL_VERIFY_TTL_MINUTES", "60")),
    PURPOSE_PASSWORD_RESET: int(os.environ.get("PASSWORD_RESET_TTL_MINUTES", "30")),
}

# Max create-token requests per request_key (hashed email) per window
_RATE_LIMIT = int(os.environ.get("AUTH_TOKEN_RATE_LIMIT", "5"))
_RATE_WINDOW_MINUTES = int(os.environ.get("AUTH_TOKEN_RATE_WINDOW_MINUTES", "60"))


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_request_key(email: str) -> str:
    normalized = (email or "").strip().lower()
    pepper = os.environ.get("JWT_SECRET", "contentos")[:32]
    return hashlib.sha256(f"{pepper}:{normalized}".encode("utf-8")).hexdigest()


def frontend_base_url() -> str:
    return (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("LINKEDIN_FRONTEND_REDIRECT", "").rsplit("/", 1)[0]
        or "http://localhost:5173"
    ).rstrip("/")


def ensure_auth_schema(session) -> None:
    """Idempotent columns/table for create_all + existing DBs (Alembic-free path)."""
    from sqlalchemy import text
    from database import get_engine

    # Prefer SQLModel create for new installs
    from database.models import SQLModel  # noqa: F401 — AuthToken registered on models import

    try:
        AuthToken.__table__.create(bind=get_engine(), checkfirst=True)
    except Exception:
        pass
    try:
        with get_engine().begin() as conn:
            for stmt in (
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0",
            ):
                try:
                    conn.execute(text(stmt))
                except Exception:
                    # SQLite older dialects may not support IF NOT EXISTS on ADD COLUMN
                    try:
                        col = "email_verified_at" if "email_verified_at" in stmt else "token_version"
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} TIMESTAMP" if col == "email_verified_at" else f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0"))
                    except Exception:
                        pass
    except Exception:
        pass


def assert_rate_limit(session, *, purpose: str, request_key: str) -> None:
    since = datetime.utcnow() - timedelta(minutes=_RATE_WINDOW_MINUTES)
    recent = session.exec(
        select(AuthToken).where(
            AuthToken.purpose == purpose,
            AuthToken.request_key == request_key,
            AuthToken.created_at >= since,
        )
    ).all()
    if len(recent) >= _RATE_LIMIT:
        # Generic message — no enumeration
        raise AppError(
            "Too many requests. Please try again later.",
            429,
            "RATE_LIMITED",
        )


def issue_token(
    session,
    *,
    user: User,
    purpose: Purpose,
    invalidate_previous: bool = True,
) -> str:
    """Create a one-time token; returns raw token (never store/log it)."""
    ensure_auth_schema(session)
    email = user.email or ""
    request_key = hash_request_key(email)
    assert_rate_limit(session, purpose=purpose, request_key=request_key)

    if invalidate_previous:
        now = datetime.utcnow()
        for row in session.exec(
            select(AuthToken).where(
                AuthToken.user_id == user.user_id,
                AuthToken.purpose == purpose,
                AuthToken.used_at.is_(None),  # type: ignore[union-attr]
            )
        ).all():
            if row.used_at is None:
                row.used_at = now
                session.add(row)

    raw = secrets.token_urlsafe(32)
    ttl = _TTL_MINUTES.get(purpose, 60)
    row = AuthToken(
        user_id=user.user_id,  # type: ignore[arg-type]
        purpose=purpose,
        token_hash=hash_token(raw),
        expires_at=datetime.utcnow() + timedelta(minutes=ttl),
        request_key=request_key,
    )
    session.add(row)
    session.flush()
    return raw


def consume_token(session, *, raw_token: str, purpose: Purpose) -> tuple[AuthToken, User]:
    if not raw_token or not str(raw_token).strip():
        raise ValidationError("Token is required")
    ensure_auth_schema(session)
    digest = hash_token(str(raw_token).strip())
    row = session.exec(
        select(AuthToken).where(
            AuthToken.token_hash == digest,
            AuthToken.purpose == purpose,
        )
    ).first()
    if not row:
        raise AppError("Invalid or expired token", 400, "INVALID_TOKEN")
    if row.used_at is not None:
        raise AppError("This link has already been used", 400, "TOKEN_USED")
    if row.expires_at < datetime.utcnow():
        raise AppError("This link has expired", 400, "TOKEN_EXPIRED")
    user = session.get(User, row.user_id)
    if not user or not user.is_active:
        raise AppError("Invalid or expired token", 400, "INVALID_TOKEN")
    row.used_at = datetime.utcnow()
    session.add(row)
    session.flush()
    return row, user


def require_email_verified(user_row: User | None) -> None:
    if user_row is None:
        raise AppError("Unauthenticated", 401, "UNAUTHORIZED")
    if user_row.email_verified_at is None:
        raise AppError(
            "Verify your email before publishing. Check your inbox or request a new link.",
            403,
            "EMAIL_UNVERIFIED",
        )


def is_local() -> bool:
    return os.environ.get("IS_LOCAL") == "true" or os.environ.get("AWS_SAM_LOCAL") == "true"
