"""Auth-related transactional emails via SES (local-safe, no raw tokens in logs)."""
from __future__ import annotations

import os
from utils.auth_tokens import frontend_base_url, is_local
from utils.logger import logger
from utils.ses_mail import send_email


def _from_email() -> str:
    return (os.environ.get("SES_FROM_EMAIL") or os.environ.get("FROM_EMAIL") or "").strip()


def send_verification_email(*, to_email: str, raw_token: str) -> dict:
    link = f"{frontend_base_url()}/verify-email?token={raw_token}"
    subject = "Verify your ContentOS email"
    text = (
        "Welcome to ContentOS.\n\n"
        "Confirm your email by opening this link (expires soon):\n"
        f"{link}\n\n"
        "If you did not create an account, ignore this message.\n"
    )
    html = (
        "<p>Welcome to ContentOS.</p>"
        "<p>Confirm your email to unlock publishing:</p>"
        f'<p><a href="{link}">Verify email</a></p>'
        "<p>If you did not create an account, you can ignore this message.</p>"
    )
    return _dispatch(to_email=to_email, subject=subject, html=html, text=text, link=link)


def send_password_reset_email(*, to_email: str, raw_token: str) -> dict:
    link = f"{frontend_base_url()}/reset-password?token={raw_token}"
    subject = "Reset your ContentOS password"
    text = (
        "We received a password reset request for your ContentOS account.\n\n"
        f"Reset link (single-use, expires soon):\n{link}\n\n"
        "If you did not request this, ignore this message.\n"
    )
    html = (
        "<p>We received a password reset request for your ContentOS account.</p>"
        f'<p><a href="{link}">Reset password</a></p>'
        "<p>If you did not request this, you can ignore this message.</p>"
    )
    return _dispatch(to_email=to_email, subject=subject, html=html, text=text, link=link)


def _dispatch(*, to_email: str, subject: str, html: str, text: str, link: str) -> dict:
    # Never log the raw token / full link
    logger.info(
        "Auth email queued",
        {"toDomain": (to_email.split("@")[-1] if "@" in to_email else None), "subject": subject},
    )
    # Ensure FROM is present for send_email path; local stub still works
    if not _from_email() and is_local():
        os.environ.setdefault("SES_FROM_EMAIL", "noreply@localhost")
    result = send_email(
        to_addresses=[to_email],
        subject=subject,
        html_body=html,
        text_body=text,
    )
    if is_local():
        # Dev-only: return link in API responses via caller — not written to logs
        result = {**result, "devLink": link}
    return result
