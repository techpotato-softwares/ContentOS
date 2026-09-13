"""Amazon SES + SMTP (Gmail/Mailpit) + local file inbox email helper."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from utils.logger import logger


def _transport() -> str:
    return (os.environ.get("EMAIL_TRANSPORT") or "").lower().strip()


def ses_enabled() -> bool:
    if _transport() in ("local", "inbox", "file", "smtp", "mailpit"):
        return False
    if _transport() == "ses":
        return True
    flag = (os.environ.get("SES_ENABLED") or "").lower().strip()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return bool(os.environ.get("SES_FROM_EMAIL")) and os.environ.get("IS_LOCAL") != "true"


def smtp_enabled() -> bool:
    transport = _transport()
    if transport in ("smtp", "mailpit"):
        return True
    if transport in ("ses", "none", "log", "local", "inbox", "file"):
        return False
    # Auto SMTP when host is set and SES is not forced on
    return bool((os.environ.get("SMTP_HOST") or "").strip()) and not ses_enabled()


def _smtp_settings() -> dict[str, str | int | bool]:
    return {
        "host": (os.environ.get("SMTP_HOST") or "127.0.0.1").strip(),
        "port": int(os.environ.get("SMTP_PORT") or "1025"),
        "user": (os.environ.get("SMTP_USER") or "").strip(),
        "password": (os.environ.get("SMTP_PASSWORD") or "").strip(),
        "use_tls": (os.environ.get("SMTP_TLS") or "true").lower().strip()
        in ("1", "true", "yes"),
    }


def _is_mailpit_host(host: str) -> bool:
    h = (host or "").lower()
    return h in ("127.0.0.1", "localhost", "mailpit") or h.endswith(".local")


def _send_via_smtp(
    *,
    from_addr: str,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None,
) -> dict:
    settings = _smtp_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addresses)
    if text_body:
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(html_body, subtype="html")

    host = str(settings["host"])
    port = int(settings["port"])
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if settings["use_tls"]:
            smtp.starttls()
        user = str(settings["user"] or "")
        password = str(settings["password"] or "")
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)

    result: dict = {
        "sent": True,
        "transport": "smtp",
        "to": to_addresses,
        "subject": subject,
    }
    # Only Mailpit gets a local inbox URL — real Gmail/Outlook does not
    if _is_mailpit_host(host):
        result["inboxUrl"] = "http://127.0.0.1:8025"
    logger.info(
        "SMTP email sent",
        {"to": to_addresses, "subject": subject, "host": host, "port": port},
    )
    return result


def send_email(
    *,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict:
    """Send via SES, real SMTP (e.g. Gmail), Mailpit, or local inbox."""
    recipients = [a.strip() for a in to_addresses if a and a.strip()]
    if not recipients:
        return {"sent": False, "reason": "no_recipients"}

    from_addr = (
        os.environ.get("SES_FROM_EMAIL")
        or os.environ.get("SMTP_FROM")
        or os.environ.get("FROM_EMAIL")
        or ""
    ).strip()
    if not from_addr:
        logger.warn("From address missing; email not sent", {"subject": subject})
        return {"sent": False, "reason": "missing_from", "preview": subject}

    from utils.local_mailbox import local_mailbox_enabled, save_local_email

    want_real = _transport() in ("ses", "smtp") or ses_enabled() or (
        smtp_enabled() and not _is_mailpit_host(str(_smtp_settings()["host"]))
    )

    # 1) Local file inbox only when explicitly requested (or default local without SES/SMTP)
    if local_mailbox_enabled() and not smtp_enabled() and not ses_enabled():
        return save_local_email(
            to_addresses=recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_addr=from_addr,
        )

    # 2) SMTP (Gmail App Password, Outlook, Mailpit, …)
    if smtp_enabled():
        try:
            return _send_via_smtp(
                from_addr=from_addr,
                to_addresses=recipients,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("SMTP send failed", {"error": str(exc), "to": recipients})
            # Do not silently swallow failures when targeting a real mailbox
            if want_real and not _is_mailpit_host(str(_smtp_settings()["host"])):
                return {"sent": False, "reason": "smtp_error", "error": str(exc)}
            if os.environ.get("IS_LOCAL") == "true":
                return save_local_email(
                    to_addresses=recipients,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                    from_addr=from_addr,
                )
            return {"sent": False, "reason": "smtp_error", "error": str(exc)}

    # 3) Amazon SES
    if not ses_enabled():
        if os.environ.get("IS_LOCAL") == "true":
            return save_local_email(
                to_addresses=recipients,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_addr=from_addr,
            )
        return {
            "sent": False,
            "reason": "ses_disabled",
            "to": recipients,
            "subject": subject,
            "preview": True,
        }

    try:
        import boto3

        region = (
            os.environ.get("AWS_REGION") or os.environ.get("SES_REGION") or "ap-south-1"
        )
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
        return {
            "sent": True,
            "messageId": message_id,
            "to": recipients,
            "transport": "ses",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("SES send failed", {"error": str(exc), "to": recipients})
        return {"sent": False, "reason": "ses_error", "error": str(exc)}
