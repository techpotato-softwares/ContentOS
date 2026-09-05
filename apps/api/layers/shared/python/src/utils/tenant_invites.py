"""Tenant team invite tokens — hashed at rest, TTL-limited, single-use."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from sqlmodel import select

from database.models import TenantInvite
from middleware.error_handler import AppError, ValidationError

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REVOKED = "revoked"

ALLOWED_INVITE_ROLES = frozenset({"tenant_member", "tenant_admin"})

_TTL_HOURS = int(os.environ.get("TENANT_INVITE_TTL_HOURS", "72"))


def hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def frontend_base_url() -> str:
    return (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("LINKEDIN_FRONTEND_REDIRECT", "").rsplit("/", 1)[0]
        or "http://localhost:5173"
    ).rstrip("/")


def is_local() -> bool:
    return os.environ.get("IS_LOCAL") == "true" or os.environ.get("AWS_SAM_LOCAL") == "true"


def ensure_invite_schema(_session=None) -> None:
    """Idempotent table create for create_all / existing DBs."""
    try:
        from database import get_engine

        TenantInvite.__table__.create(bind=get_engine(), checkfirst=True)
    except Exception:
        pass


def normalize_invite_role(role: str | None) -> str:
    name = (role or "tenant_member").strip().lower()
    if name not in ALLOWED_INVITE_ROLES:
        raise ValidationError(
            f"role must be one of: {', '.join(sorted(ALLOWED_INVITE_ROLES))}"
        )
    return name


def issue_invite_token(
    session,
    *,
    tenant_id: int,
    email: str,
    role: str,
    invited_by: int | None,
) -> tuple[TenantInvite, str]:
    """Create pending invite; returns (row, raw_token). Raw token must not be logged."""
    ensure_invite_schema(session)
    email_n = (email or "").strip().lower()
    if not email_n or "@" not in email_n:
        raise ValidationError("Valid email is required")
    role_n = normalize_invite_role(role)

    # Revoke prior pending invites for same email+tenant
    now = datetime.utcnow()
    for prior in session.exec(
        select(TenantInvite).where(
            TenantInvite.tenant_id == tenant_id,
            TenantInvite.email == email_n,
            TenantInvite.status == STATUS_PENDING,
        )
    ).all():
        prior.status = STATUS_REVOKED
        prior.updated_at = now
        session.add(prior)

    raw = secrets.token_urlsafe(32)
    row = TenantInvite(
        tenant_id=tenant_id,
        email=email_n,
        role=role_n,
        token=hash_invite_token(raw),
        expires_at=now + timedelta(hours=_TTL_HOURS),
        invited_by=invited_by,
        status=STATUS_PENDING,
    )
    session.add(row)
    session.flush()
    return row, raw


def load_invite_by_raw_token(session, raw_token: str) -> TenantInvite:
    if not raw_token or not str(raw_token).strip():
        raise ValidationError("Invite token is required")
    ensure_invite_schema(session)
    digest = hash_invite_token(str(raw_token).strip())
    row = session.exec(
        select(TenantInvite).where(TenantInvite.token == digest)
    ).first()
    if not row:
        raise AppError("Invalid or expired invite", 400, "INVALID_INVITE")
    return row


def assert_invite_acceptable(row: TenantInvite) -> None:
    if row.status == STATUS_REVOKED:
        raise AppError("This invite has been revoked", 400, "INVITE_REVOKED")
    if row.status == STATUS_ACCEPTED:
        raise AppError("This invite has already been used", 400, "INVITE_USED")
    if row.status != STATUS_PENDING:
        raise AppError("Invalid or expired invite", 400, "INVALID_INVITE")
    if row.expires_at < datetime.utcnow():
        raise AppError("This invite has expired", 400, "INVITE_EXPIRED")


def invite_public_dict(row: TenantInvite, *, tenant_name: str | None = None) -> dict:
    return {
        "inviteId": row.invite_id,
        "email": row.email,
        "role": row.role,
        "status": row.status,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "invitedBy": row.invited_by,
        "tenantId": row.tenant_id,
        "tenantName": tenant_name,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
