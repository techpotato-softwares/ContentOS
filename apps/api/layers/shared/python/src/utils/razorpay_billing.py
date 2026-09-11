"""Razorpay subscriptions / payment links / webhooks (idempotent plan sync)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from database.models import RazorpayWebhookEvent, Tenant
from middleware.error_handler import AppError, ValidationError
from sqlmodel import Session, select

from utils.ai_billing import (
    PLAN_CATALOG,
    apply_plan_to_tenant,
    assert_can_subscribe,
    get_plan,
)
from utils.logger import logger
from utils.razorpay_secrets import (
    get_razorpay_secrets,
    plan_id_to_plan_tier,
    plan_tier_to_plan_id,
    require_razorpay_configured,
)

_API = "https://api.razorpay.com/v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _frontend_origin() -> str:
    return (
        os.environ.get("BILLING_FRONTEND_URL")
        or os.environ.get("LINKEDIN_FRONTEND_REDIRECT")
        or os.environ.get("PUBLIC_WEB_URL")
        or "http://localhost:5173"
    ).rstrip("/")


def _auth() -> tuple[str, str]:
    secrets = require_razorpay_configured()
    return secrets.key_id, secrets.key_secret


def _request(method: str, path: str, *, json_body: dict | None = None) -> dict[str, Any]:
    url = f"{_API}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, url, auth=_auth(), json=json_body)
    except httpx.HTTPError as exc:
        logger.warn("Razorpay HTTP error", {"error_type": type(exc).__name__, "path": path})
        raise AppError("Razorpay request failed", 502, "RAZORPAY_UPSTREAM") from exc
    if resp.status_code >= 400:
        # Never log response body (may contain PII); surface a safe code only.
        logger.warn(
            "Razorpay API error",
            {"status": resp.status_code, "path": path},
        )
        raise AppError("Razorpay API error", 502, "RAZORPAY_UPSTREAM")
    data = resp.json()
    if not isinstance(data, dict):
        raise AppError("Unexpected Razorpay response", 502, "RAZORPAY_UPSTREAM")
    return data


def ensure_razorpay_customer(
    session: Session, tenant: Tenant, email: str | None
) -> str:
    if tenant.razorpay_customer_id:
        return tenant.razorpay_customer_id
    payload: dict[str, Any] = {
        "name": tenant.name or f"Tenant {tenant.tenant_id}",
        "fail_existing": "0",
        "notes": {
            "tenant_id": str(tenant.tenant_id),
            "tenant_slug": tenant.slug or "",
        },
    }
    if email:
        payload["email"] = email
    customer = _request("POST", "/customers", json_body=payload)
    cid = customer.get("id")
    if not cid:
        raise AppError("Razorpay customer creation failed", 502, "RAZORPAY_UPSTREAM")
    tenant.razorpay_customer_id = cid
    tenant.updated_at = _utcnow()
    session.add(tenant)
    session.flush()
    return cid


def create_subscription(
    session: Session,
    *,
    tenant: Tenant,
    plan_tier: str,
    customer_email: str | None,
    total_count: int = 120,
) -> dict[str, str]:
    """Create a Razorpay subscription; returns Checkout short_url (INR/UPI/cards)."""
    assert_can_subscribe(tenant, "razorpay")
    plan = get_plan(plan_tier)
    plan_id = plan_tier_to_plan_id(plan_tier)
    customer_id = ensure_razorpay_customer(session, tenant, customer_email)
    sub = _request(
        "POST",
        "/subscriptions",
        json_body={
            "plan_id": plan_id,
            "customer_id": customer_id,
            "total_count": total_count,
            "customer_notify": 1,
            "notes": {
                "tenant_id": str(tenant.tenant_id),
                "plan_tier": plan["id"],
                "monthly_inr": str(plan["monthly_inr"]),
            },
        },
    )
    sub_id = sub.get("id")
    short_url = sub.get("short_url") or ""
    if not sub_id:
        raise AppError("Razorpay subscription creation failed", 502, "RAZORPAY_UPSTREAM")
    tenant.razorpay_subscription_id = sub_id
    tenant.billing_gateway = "razorpay"
    # Pending until webhook activates; do not grant quota until charged/activated.
    if (tenant.billing_status or "none") == "none":
        tenant.billing_status = "incomplete"
    tenant.updated_at = _utcnow()
    session.add(tenant)
    return {
        "url": short_url,
        "subscriptionId": sub_id,
        "gateway": "razorpay",
        "currency": "INR",
        "amountInr": str(plan["monthly_inr"]),
    }


def create_payment_link(
    session: Session,
    *,
    tenant: Tenant,
    plan_tier: str,
    customer_email: str | None,
    success_url: str | None = None,
) -> dict[str, str]:
    """INR payment link (UPI + cards). Notes carry plan_tier for webhook sync."""
    assert_can_subscribe(tenant, "razorpay")
    plan = get_plan(plan_tier)
    customer_id = ensure_razorpay_customer(session, tenant, customer_email)
    origin = _frontend_origin()
    callback = success_url or f"{origin}/settings/billing?checkout=success&gateway=razorpay"
    amount_paise = int(plan["monthly_inr"]) * 100
    link = _request(
        "POST",
        "/payment_links",
        json_body={
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": f"ContentOS {plan['label']} — ₹{plan['monthly_inr']}/mo",
            "customer": {
                "name": tenant.name or f"Tenant {tenant.tenant_id}",
                **({"email": customer_email} if customer_email else {}),
            },
            "notify": {"sms": False, "email": bool(customer_email)},
            "reminder_enable": True,
            "callback_url": callback,
            "callback_method": "get",
            "notes": {
                "tenant_id": str(tenant.tenant_id),
                "plan_tier": plan["id"],
                "monthly_inr": str(plan["monthly_inr"]),
                "razorpay_customer_id": customer_id,
            },
            # Prefer UPI + cards in Checkout
            "options": {
                "checkout": {
                    "name": "ContentOS",
                    "method": {
                        "upi": True,
                        "card": True,
                        "netbanking": True,
                        "wallet": False,
                    },
                }
            },
        },
    )
    url = link.get("short_url") or ""
    link_id = link.get("id") or ""
    if not url:
        raise AppError("Razorpay payment link creation failed", 502, "RAZORPAY_UPSTREAM")
    tenant.billing_gateway = "razorpay"
    if (tenant.billing_status or "none") == "none":
        tenant.billing_status = "incomplete"
    tenant.updated_at = _utcnow()
    session.add(tenant)
    return {
        "url": url,
        "paymentLinkId": link_id,
        "gateway": "razorpay",
        "currency": "INR",
        "amountInr": str(plan["monthly_inr"]),
    }


def cancel_subscription(session: Session, *, tenant: Tenant, cancel_at_cycle_end: bool = False) -> dict[str, Any]:
    require_razorpay_configured()
    sub_id = tenant.razorpay_subscription_id
    if not sub_id:
        raise ValidationError("No Razorpay subscription on this tenant")
    path = f"/subscriptions/{sub_id}/cancel"
    body = {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0}
    _request("POST", path, json_body=body)
    if not cancel_at_cycle_end:
        tenant.billing_status = "canceled"
        tenant.razorpay_subscription_id = None
        if (tenant.billing_gateway or "").lower() == "razorpay":
            tenant.billing_gateway = None
        tenant.updated_at = _utcnow()
        session.add(tenant)
    return {"canceled": True, "subscriptionId": sub_id}


def _map_subscription_status(status: str | None) -> str:
    s = (status or "none").strip().lower()
    mapping = {
        "created": "incomplete",
        "authenticated": "incomplete",
        "active": "active",
        "pending": "past_due",
        "halted": "past_due",
        "cancelled": "canceled",
        "canceled": "canceled",
        "completed": "canceled",
        "expired": "canceled",
        "paused": "paused",
    }
    return mapping.get(s, "none")


def sync_tenant_from_subscription(
    session: Session,
    *,
    subscription: dict[str, Any],
    tenant_id: int | None = None,
) -> Tenant | None:
    secrets = get_razorpay_secrets()
    notes = subscription.get("notes") or {}
    tid = tenant_id
    if tid is None and notes.get("tenant_id"):
        try:
            tid = int(notes["tenant_id"])
        except (TypeError, ValueError):
            tid = None

    tenant: Tenant | None = None
    if tid is not None:
        tenant = session.get(Tenant, tid)
    if tenant is None:
        customer_id = subscription.get("customer_id") or subscription.get("customer")
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("id")
        if customer_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.razorpay_customer_id == customer_id)
            ).first()
    if tenant is None:
        sub_id = subscription.get("id")
        if sub_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.razorpay_subscription_id == sub_id)
            ).first()
    if tenant is None:
        logger.warn(
            "Razorpay subscription sync: tenant not found",
            {"subscription_id": subscription.get("id"), "has_notes_tenant": bool(notes.get("tenant_id"))},
        )
        return None

    plan_id = subscription.get("plan_id")
    tier = (
        plan_id_to_plan_tier(plan_id, secrets)
        or notes.get("plan_tier")
        or tenant.plan_tier
    )
    try:
        apply_plan_to_tenant(tenant, tier)
    except ValidationError:
        logger.warn("Razorpay sync: unknown plan tier", {"tier": tier})

    tenant.razorpay_subscription_id = subscription.get("id") or tenant.razorpay_subscription_id
    customer = subscription.get("customer_id") or subscription.get("customer")
    if isinstance(customer, dict):
        customer = customer.get("id")
    if customer:
        tenant.razorpay_customer_id = customer
    tenant.billing_gateway = "razorpay"
    tenant.billing_status = _map_subscription_status(subscription.get("status"))
    tenant.updated_at = _utcnow()
    session.add(tenant)
    return tenant


def _apply_plan_from_notes(session: Session, notes: dict[str, Any], *, status: str = "active") -> Tenant | None:
    tid_raw = notes.get("tenant_id")
    if not tid_raw:
        return None
    try:
        tid = int(tid_raw)
    except (TypeError, ValueError):
        return None
    tenant = session.get(Tenant, tid)
    if not tenant:
        return None
    tier = notes.get("plan_tier")
    if tier and tier in PLAN_CATALOG:
        apply_plan_to_tenant(tenant, tier)
    if notes.get("razorpay_customer_id"):
        tenant.razorpay_customer_id = notes["razorpay_customer_id"]
    tenant.billing_gateway = "razorpay"
    tenant.billing_status = status
    tenant.updated_at = _utcnow()
    session.add(tenant)
    return tenant


def _event_idempotency_key(event: dict[str, Any]) -> str:
    if event.get("id"):
        return str(event["id"])
    event_type = event.get("event") or "unknown"
    created = event.get("created_at") or 0
    # Stable hash of type + created + nested entity id when Razorpay omits event id.
    payload = event.get("payload") or {}
    entity_id = ""
    for key in ("subscription", "payment", "payment_link", "invoice", "order"):
        block = payload.get(key) or {}
        entity = block.get("entity") if isinstance(block, dict) else None
        if isinstance(entity, dict) and entity.get("id"):
            entity_id = str(entity["id"])
            break
    raw = f"{event_type}:{created}:{entity_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def process_razorpay_event(session: Session, event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("event") or ""
    event_id = _event_idempotency_key(event)
    existing = session.exec(
        select(RazorpayWebhookEvent).where(RazorpayWebhookEvent.event_id == event_id)
    ).first()
    if existing:
        return {"duplicate": True, "eventId": event_id, "type": event_type}

    session.add(
        RazorpayWebhookEvent(
            event_id=event_id, event_type=event_type, processed_at=_utcnow()
        )
    )
    session.flush()

    payload = event.get("payload") or {}
    summary: dict[str, Any] = {"duplicate": False, "eventId": event_id, "type": event_type}

    def _entity(name: str) -> dict[str, Any]:
        block = payload.get(name) or {}
        entity = block.get("entity") if isinstance(block, dict) else None
        return entity if isinstance(entity, dict) else {}

    if event_type in (
        "subscription.activated",
        "subscription.charged",
        "subscription.updated",
        "subscription.pending",
        "subscription.halted",
        "subscription.paused",
        "subscription.resumed",
        "subscription.cancelled",
        "subscription.completed",
    ):
        sub = _entity("subscription")
        tenant = sync_tenant_from_subscription(session, subscription=sub)
        if event_type == "subscription.cancelled" and tenant:
            tenant.billing_status = "canceled"
            tenant.razorpay_subscription_id = None
            if (tenant.billing_gateway or "").lower() == "razorpay":
                tenant.billing_gateway = None
            session.add(tenant)
        if event_type in ("subscription.pending", "subscription.halted") and tenant:
            tenant.billing_status = "past_due"
            session.add(tenant)
        summary["tenantId"] = tenant.tenant_id if tenant else None

    elif event_type in ("payment.failed", "invoice.payment_failed"):
        payment = _entity("payment") or _entity("invoice")
        notes = payment.get("notes") or {}
        tenant = _apply_plan_from_notes(session, notes, status="past_due")
        if tenant is None:
            # Try subscription id on payment
            sub_id = payment.get("subscription_id")
            if sub_id:
                tenant = session.exec(
                    select(Tenant).where(Tenant.razorpay_subscription_id == sub_id)
                ).first()
                if tenant:
                    tenant.billing_status = "past_due"
                    tenant.updated_at = _utcnow()
                    session.add(tenant)
        summary["tenantId"] = tenant.tenant_id if tenant else None

    elif event_type in ("payment.captured", "payment_link.paid", "invoice.paid"):
        payment = _entity("payment") or _entity("payment_link") or _entity("invoice")
        notes = payment.get("notes") or {}
        tenant = _apply_plan_from_notes(session, notes, status="active")
        summary["tenantId"] = tenant.tenant_id if tenant else None

    else:
        summary["ignored"] = True

    return summary


def verify_webhook_signature(payload: bytes | str, signature: str | None) -> dict[str, Any]:
    secrets = require_razorpay_configured()
    if not secrets.webhook_secret:
        raise AppError("Razorpay webhook secret is not configured", 503, "RAZORPAY_NOT_CONFIGURED")
    if not signature:
        raise AppError("Missing X-Razorpay-Signature header", 400, "RAZORPAY_SIGNATURE_MISSING")
    body = payload if isinstance(payload, (bytes, bytearray)) else payload.encode("utf-8")
    expected = hmac.new(
        secrets.webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature.strip()):
        logger.warn("Razorpay webhook signature verification failed", {"error_type": "SignatureMismatch"})
        raise AppError("Invalid Razorpay signature", 400, "RAZORPAY_SIGNATURE_INVALID")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppError("Invalid webhook JSON", 400, "RAZORPAY_PAYLOAD_INVALID") from exc
    if not isinstance(data, dict):
        raise AppError("Invalid webhook JSON", 400, "RAZORPAY_PAYLOAD_INVALID")
    return data
