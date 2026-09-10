"""Tenant team invites — hashed single-use tokens, email delivery, accept helpers."""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import select

from database.models import Role, Tenant, TenantInvite, User
from middleware.error_handler import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from utils.logger import logger
from utils.ses_mail import send_email

ALLOWED_INVITE_ROLES = frozenset({"tenant_member", "tenant_admin"})
INVITE_TTL_DAYS = 7
INVITE_STATUSES = frozenset({"pending", "accepted", "revoked", "expired"})


def hash_invite_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def frontend_base_url() -> str:
    return (
        os.environ.get("INVITE_FRONTEND_URL")
        or os.environ.get("BILLING_FRONTEND_URL")
        or os.environ.get("LINKEDIN_FRONTEND_REDIRECT", "http://localhost:5173").rsplit(
            "/connections", 1
        )[0]
        or "http://localhost:5173"
    ).rstrip("/")


def invite_accept_url(raw_token: str) -> str:
    return f"{frontend_base_url()}/invite/accept?token={raw_token}"


def invite_public(invite: TenantInvite, *, tenant_name: str | None = None) -> dict[str, Any]:
    """Safe serializer — never includes raw or hashed token."""
    return {
        "inviteId": invite.invite_id,
        "email": invite.email,
        "role": invite.role,
        "status": invite.status,
        "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None,
        "invitedBy": invite.invited_by,
        "tenantId": invite.tenant_id,
        "tenantName": tenant_name,
        "createdAt": invite.created_at.isoformat() if invite.created_at else None,
        "acceptedAt": invite.accepted_at.isoformat() if invite.accepted_at else None,
    }


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _normalize_role(role: str | None) -> str:
    key = (role or "tenant_member").strip().lower()
    if key in ("member", "user"):
        key = "tenant_member"
    if key in ("admin",):
        key = "tenant_admin"
    if key not in ALLOWED_INVITE_ROLES:
        raise ValidationError("role must be tenant_member or tenant_admin")
    return key


def mark_expired_if_needed(invite: TenantInvite, now: datetime | None = None) -> TenantInvite:
    now = now or datetime.utcnow()
    if invite.status == "pending" and invite.expires_at and invite.expires_at < now:
        invite.status = "expired"
        invite.updated_at = now
    return invite


def get_role_by_name(session, role_name: str) -> Role:
    role = session.exec(select(Role).where(Role.role_name == role_name)).first()
    if not role:
        raise AppError(
            f"Role '{role_name}' is not configured. Run seed or register once to bootstrap RBAC.",
            500,
            "SETUP",
        )
    return role


def find_pending_invite(session, *, tenant_id: int, email: str) -> TenantInvite | None:
    email = _normalize_email(email)
    rows = session.exec(
        select(TenantInvite).where(
            TenantInvite.tenant_id == tenant_id,
            TenantInvite.email == email,
            TenantInvite.status == "pending",
        )
    ).all()
    now = datetime.utcnow()
    for inv in rows:
        mark_expired_if_needed(inv, now)
        if inv.status == "pending":
            return inv
    return None


def create_or_refresh_invite(
    session,
    *,
    tenant: Tenant,
    email: str,
    role: str,
    invited_by: int | None,
) -> tuple[TenantInvite, str]:
    """Create invite or rotate token on existing pending. Returns (invite, raw_token)."""
    email = _normalize_email(email)
    if not email or "@" not in email:
        raise ValidationError("A valid email is required")
    role = _normalize_role(role)

    existing_user = session.exec(select(User).where(User.email == email)).first()
    if existing_user and existing_user.tenant_id == tenant.tenant_id:
        raise ConflictError("This user is already a member of your workspace")

    raw = generate_invite_token()
    token_hash = hash_invite_token(raw)
    now = datetime.utcnow()
    expires = now + timedelta(days=INVITE_TTL_DAYS)

    pending = find_pending_invite(session, tenant_id=int(tenant.tenant_id), email=email)
    if pending:
        pending.token = token_hash
        pending.role = role
        pending.expires_at = expires
        pending.invited_by = invited_by
        pending.status = "pending"
        pending.updated_at = now
        session.add(pending)
        return pending, raw

    invite = TenantInvite(
        tenant_id=int(tenant.tenant_id),
        email=email,
        role=role,
        token=token_hash,
        expires_at=expires,
        invited_by=invited_by,
        status="pending",
    )
    session.add(invite)
    session.flush()
    return invite, raw


def send_invite_email(
    *,
    tenant: Tenant,
    invite: TenantInvite,
    raw_token: str,
    inviter_name: str | None = None,
) -> dict:
    from utils.ses_mail import ses_enabled

    accept_url = invite_accept_url(raw_token)
    tenant_label = tenant.app_display_name or tenant.name
    subject = f"You're invited to {tenant_label} on ContentOS"
    inviter = inviter_name or "A teammate"
    text = (
        f"{inviter} invited you to join {tenant_label} on ContentOS "
        f"as {invite.role.replace('_', ' ')}.\n\n"
        f"Accept your invite:\n{accept_url}\n\n"
        f"This link expires at {invite.expires_at.isoformat()}Z and can be used once."
    )
    html = f"""
    <p><strong>{inviter}</strong> invited you to join <strong>{tenant_label}</strong> on ContentOS
    as <strong>{invite.role.replace('_', ' ')}</strong>.</p>
    <p><a href="{accept_url}">Accept invite</a></p>
    <p style="color:#666;font-size:12px">This link expires at {invite.expires_at.isoformat()}Z and can be used once.</p>
    """
    # Avoid SES helper's textPreview log (would leak the raw token in the URL)
    if not ses_enabled():
        logger.info(
            "Invite email preview (SES disabled) — accept URL not logged",
            {
                "inviteId": invite.invite_id,
                "tenantId": invite.tenant_id,
                "email": invite.email,
                "subject": subject,
            },
        )
        return {
            "sent": False,
            "reason": "ses_disabled",
            "to": [invite.email],
            "subject": subject,
            "preview": True,
        }

    result = send_email(
        to_addresses=[invite.email],
        subject=subject,
        html_body=html,
        text_body=text,
    )
    logger.info(
        "Invite email attempted",
        {
            "inviteId": invite.invite_id,
            "tenantId": invite.tenant_id,
            "email": invite.email,
            "sent": bool(result.get("sent")),
            "reason": result.get("reason"),
        },
    )
    return result


def load_invite_by_raw_token(session, raw_token: str) -> TenantInvite:
    raw = (raw_token or "").strip()
    if not raw:
        raise ValidationError("token is required")
    token_hash = hash_invite_token(raw)
    invite = session.exec(select(TenantInvite).where(TenantInvite.token == token_hash)).first()
    if not invite:
        raise NotFoundError("Invite not found or invalid")
    mark_expired_if_needed(invite)
    if invite.status == "revoked":
        raise AppError("This invite has been revoked", 410, "INVITE_REVOKED")
    if invite.status == "accepted":
        raise AppError("This invite has already been used", 410, "INVITE_USED")
    if invite.status == "expired" or (
        invite.expires_at and invite.expires_at < datetime.utcnow()
    ):
        invite.status = "expired"
        raise AppError("This invite has expired", 410, "INVITE_EXPIRED")
    if invite.status != "pending":
        raise AppError("Invite is not available", 410, "INVITE_INVALID")
    return invite


def assert_invite_email_matches(invite: TenantInvite, email: str) -> None:
    if _normalize_email(invite.email) != _normalize_email(email):
        raise ForbiddenError("This invite was sent to a different email address")


def accept_invite_for_user(session, invite: TenantInvite, user: User) -> User:
    """Attach authenticated/existing user to invite tenant. Enforces email + single-tenant rules."""
    assert_invite_email_matches(invite, user.email)
    tenant = session.get(Tenant, invite.tenant_id)
    if not tenant or not tenant.is_active:
        raise NotFoundError("Tenant not found")

    if user.tenant_id and int(user.tenant_id) != int(invite.tenant_id):
        raise ConflictError(
            "You already belong to another workspace. Leave it before accepting this invite."
        )

    role = get_role_by_name(session, invite.role)
    now = datetime.utcnow()
    user.tenant_id = invite.tenant_id
    user.role_id = role.role_id
    user.updated_at = now
    invite.status = "accepted"
    invite.accepted_by_user_id = user.user_id
    invite.accepted_at = now
    invite.updated_at = now
    session.add(user)
    session.add(invite)
    return user
