"""Tenant invite transactional email via SES (local-safe; no raw tokens in logs)."""
from __future__ import annotations

import os

from utils.logger import logger
from utils.ses_mail import send_email
from utils.tenant_invites import frontend_base_url, is_local


def _from_email() -> str:
    return (
        os.environ.get("SES_FROM_EMAIL") or os.environ.get("FROM_EMAIL") or ""
    ).strip()


def send_tenant_invite_email(
    *,
    to_email: str,
    raw_token: str,
    tenant_name: str,
    role: str,
) -> dict:
    link = f"{frontend_base_url()}/accept-invite?token={raw_token}"
    subject = f"You're invited to {tenant_name} on ContentOS"
    text = (
        f"You've been invited to join {tenant_name} on ContentOS as {role}.\n\n"
        f"Accept your invite (expires soon):\n{link}\n\n"
        "If you were not expecting this, you can ignore this message.\n"
    )
    html = (
        f"<p>You've been invited to join <strong>{tenant_name}</strong> "
        f"on ContentOS as <strong>{role}</strong>.</p>"
        f'<p><a href="{link}">Accept invite</a></p>'
        "<p>If you were not expecting this, you can ignore this message.</p>"
    )
    logger.info(
        "Tenant invite email queued",
        {
            "toDomain": (to_email.split("@")[-1] if "@" in to_email else None),
            "subject": subject,
        },
    )
    if not _from_email() and is_local():
        os.environ.setdefault("SES_FROM_EMAIL", "noreply@localhost")
    result = send_email(
        to_addresses=[to_email],
        subject=subject,
        html_body=html,
        text_body=text,
    )
    if is_local():
        result = {**result, "devLink": link}
    return result
