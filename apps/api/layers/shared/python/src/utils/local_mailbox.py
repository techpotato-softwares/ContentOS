"""Local-only OTP/email inbox (no Docker/Mailpit required).

Stores messages under apps/api/media/mail_inbox/.
Open http://127.0.0.1:4001/dev/mailbox to read OTPs.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from utils.logger import logger

# utils -> src -> python -> shared -> layers -> api
_API_ROOT = Path(__file__).resolve().parents[5]


def inbox_dir() -> Path:
    override = (os.environ.get("MAIL_INBOX_DIR") or "").strip()
    path = Path(override) if override else (_API_ROOT / "media" / "mail_inbox")
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_mailbox_enabled() -> bool:
    transport = (os.environ.get("EMAIL_TRANSPORT") or "").lower().strip()
    if transport in ("local", "inbox", "file"):
        return True
    if transport in ("smtp", "mailpit", "ses"):
        return False
    # Default local fallback when not using SMTP/SES explicitly
    return os.environ.get("IS_LOCAL") == "true"


def save_local_email(
    *,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
    from_addr: str = "",
) -> dict:
    mid = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    record = {
        "id": mid,
        "createdAt": created,
        "from": from_addr,
        "to": to_addresses,
        "subject": subject,
        "text": text_body or "",
        "html": html_body or "",
    }
    safe_ts = created.replace(":", "-")
    path = inbox_dir() / f"{safe_ts}_{mid}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    logger.info(
        "Local mailbox message saved",
        {"id": mid, "to": to_addresses, "subject": subject},
    )
    return {
        "sent": True,
        "transport": "local",
        "id": mid,
        "to": to_addresses,
        "inboxUrl": "http://127.0.0.1:4001/dev/mailbox",
    }


def list_messages(limit: int = 50) -> list[dict]:
    files = sorted(inbox_dir().glob("*.json"), reverse=True)
    out: list[dict] = []
    for f in files[:limit]:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
    return out


def extract_otp_codes(text: str) -> list[str]:
    return re.findall(r"\b(\d{4,8})\b", text or "")
