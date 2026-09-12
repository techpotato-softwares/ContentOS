"""Amazon SES email helper (local-safe)."""
from __future__ import annotations
import os
from utils.logger import logger


def ses_enabled() -> bool:
    flag = (os.environ.get("SES_ENABLED") or "").lower().strip()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    # Default: enable in non-local when FROM is set
    return bool(os.environ.get("SES_FROM_EMAIL")) and os.environ.get("IS_LOCAL") != "true"


def send_email(
    *,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict:
    """Send via SES, or log when disabled / local without SES_ENABLED."""
    recipients = [a.strip() for a in to_addresses if a and a.strip()]
    if not recipients:
        return {"sent": False, "reason": "no_recipients"}

    from_addr = (
        os.environ.get("SES_FROM_EMAIL") or os.environ.get("FROM_EMAIL") or ""
    ).strip()
    if not from_addr:
        logger.warn("SES_FROM_EMAIL/FROM_EMAIL missing; email not sent", {"subject": subject})
        return {"sent": False, "reason": "missing_from", "preview": subject}

    if not ses_enabled():
        # Never include raw secrets/tokens in logs — truncate and strip query tokens
        preview_src = text_body or html_body or ""
        safe_preview = preview_src
        if "token=" in safe_preview:
            import re

            safe_preview = re.sub(r"(token=)[^&\s\"']+", r"\1[REDACTED]", safe_preview)
        logger.info(
            "SES disabled — email preview only",
            {
                "toCount": len(recipients),
                "subject": subject,
                "textPreview": safe_preview[:200],
            },
        )
        return {
            "sent": False,
            "reason": "ses_disabled",
            "to": recipients,
            "subject": subject,
            "preview": True,
        }

    import boto3

    region = os.environ.get("AWS_REGION") or os.environ.get("SES_REGION") or "ap-south-1"
    client = boto3.client("ses", region_name=region)
    body: dict = {"Html": {"Charset": "UTF-8", "Data": html_body}}
    if text_body:
        body["Text"] = {"Charset": "UTF-8", "Data": text_body}

    resp = client.send_email(
        Source=from_addr,
        Destination={"ToAddresses": recipients},
        Message={
            "Subject": {"Charset": "UTF-8", "Data": subject},
            "Body": body,
        },
    )
    message_id = resp.get("MessageId")
    logger.info("SES email sent", {"messageId": message_id, "to": recipients})
    return {"sent": True, "messageId": message_id, "to": recipients}
