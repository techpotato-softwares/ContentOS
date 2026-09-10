"""Stripe Checkout / Portal / webhook sync (idempotent, transaction-safe)."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from database.models import StripeWebhookEvent, Tenant
from middleware.error_handler import AppError, NotFoundError, ValidationError
from utils.ai_billing import apply_plan_to_tenant
from utils.logger import logger
from utils.stripe_secrets import (
    get_stripe,
    get_stripe_secrets,
    plan_tier_to_price_id,
    price_id_to_plan_tier,
    require_stripe_configured,
)


def _frontend_origin() -> str:
    return (
        os.environ.get("BILLING_FRONTEND_URL")
        or os.environ.get("LINKEDIN_FRONTEND_REDIRECT")
        or os.environ.get("PUBLIC_WEB_URL")
        or "http://localhost:5173"
    ).rstrip("/")


def ensure_stripe_customer(session: Session, tenant: Tenant, email: str | None) -> str:
    if tenant.stripe_customer_id:
        return tenant.stripe_customer_id
    stripe = get_stripe()
    customer = stripe.Customer.create(
        name=tenant.name,
        email=email or None,
        metadata={"tenant_id": str(tenant.tenant_id), "tenant_slug": tenant.slug},
    )
    tenant.stripe_customer_id = customer["id"]
    tenant.updated_at = datetime.utcnow()
    session.add(tenant)
    session.flush()
    return tenant.stripe_customer_id


def create_checkout_session(
    session: Session,
    *,
    tenant: Tenant,
    plan_tier: str,
    customer_email: str | None,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, str]:
    require_stripe_configured()
    price_id = plan_tier_to_price_id(plan_tier)
    customer_id = ensure_stripe_customer(session, tenant, customer_email)
    origin = _frontend_origin()
    stripe = get_stripe()
    checkout = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url
        or f"{origin}/settings/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=cancel_url or f"{origin}/settings/billing?checkout=cancel",
        client_reference_id=str(tenant.tenant_id),
        metadata={"tenant_id": str(tenant.tenant_id), "plan_tier": plan_tier},
        subscription_data={"metadata": {"tenant_id": str(tenant.tenant_id), "plan_tier": plan_tier}},
        allow_promotion_codes=True,
    )
    return {"url": checkout["url"], "sessionId": checkout["id"]}


def create_portal_session(session: Session, *, tenant: Tenant) -> dict[str, str]:
    require_stripe_configured()
    if not tenant.stripe_customer_id:
        raise ValidationError("No Stripe customer on this tenant. Start a checkout first.")
    origin = _frontend_origin()
    stripe = get_stripe()
    portal = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=f"{origin}/settings/billing",
    )
    return {"url": portal["url"]}


def _subscription_price_id(subscription: dict[str, Any]) -> str | None:
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price") or {}
    if isinstance(price, str):
        return price
    return price.get("id")


def _map_subscription_status(status: str | None) -> str:
    s = (status or "none").strip().lower()
    allowed = {
        "trialing",
        "active",
        "past_due",
        "canceled",
        "unpaid",
        "incomplete",
        "incomplete_expired",
        "paused",
    }
    return s if s in allowed else "none"


def sync_tenant_from_subscription(
    session: Session,
    *,
    subscription: dict[str, Any],
    tenant_id: int | None = None,
) -> Tenant | None:
    secrets = get_stripe_secrets()
    meta = subscription.get("metadata") or {}
    tid = tenant_id
    if tid is None and meta.get("tenant_id"):
        try:
            tid = int(meta["tenant_id"])
        except (TypeError, ValueError):
            tid = None

    tenant: Tenant | None = None
    if tid is not None:
        tenant = session.get(Tenant, tid)
    if tenant is None:
        customer_id = subscription.get("customer")
        if isinstance(customer_id, dict):
            customer_id = customer_id.get("id")
        if customer_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            ).first()
    if tenant is None:
        logger.warn(
            "Stripe subscription sync: tenant not found",
            {"subscription_id": subscription.get("id"), "has_meta_tenant": bool(meta.get("tenant_id"))},
        )
        return None

    price_id = _subscription_price_id(subscription)
    tier = price_id_to_plan_tier(price_id, secrets) or meta.get("plan_tier") or tenant.plan_tier
    try:
        apply_plan_to_tenant(tenant, tier)
    except ValidationError:
        logger.warn("Stripe sync: unknown plan tier", {"tier": tier})

    tenant.stripe_subscription_id = subscription.get("id") or tenant.stripe_subscription_id
    customer = subscription.get("customer")
    if isinstance(customer, dict):
        customer = customer.get("id")
    if customer:
        tenant.stripe_customer_id = customer
    tenant.billing_status = _map_subscription_status(subscription.get("status"))
    tenant.updated_at = datetime.utcnow()
    session.add(tenant)
    return tenant


def _find_tenant_for_invoice(session: Session, invoice: dict[str, Any]) -> Tenant | None:
    customer_id = invoice.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    if customer_id:
        tenant = session.exec(
            select(Tenant).where(Tenant.stripe_customer_id == customer_id)
        ).first()
        if tenant:
            return tenant
    sub = invoice.get("subscription")
    if isinstance(sub, dict):
        sub = sub.get("id")
    if sub:
        return session.exec(
            select(Tenant).where(Tenant.stripe_subscription_id == sub)
        ).first()
    return None


def process_stripe_event(session: Session, event: dict[str, Any]) -> dict[str, Any]:
    """Apply a verified Stripe event. Caller owns commit/rollback.

    Returns a small safe summary (no secret/payload dump).
    """
    event_id = event.get("id")
    event_type = event.get("type") or ""
    if not event_id:
        raise ValidationError("Stripe event missing id")

    existing = session.exec(
        select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == event_id)
    ).first()
    if existing:
        return {"duplicate": True, "eventId": event_id, "type": event_type}

    session.add(
        StripeWebhookEvent(event_id=event_id, event_type=event_type, processed_at=datetime.utcnow())
    )
    # Flush early so concurrent workers hit unique constraint instead of double-applying.
    session.flush()

    data_object = (event.get("data") or {}).get("object") or {}
    summary: dict[str, Any] = {"duplicate": False, "eventId": event_id, "type": event_type}

    if event_type == "checkout.session.completed":
        sub_id = data_object.get("subscription")
        tenant_id = None
        meta = data_object.get("metadata") or {}
        if meta.get("tenant_id"):
            try:
                tenant_id = int(meta["tenant_id"])
            except (TypeError, ValueError):
                tenant_id = None
        if not tenant_id and data_object.get("client_reference_id"):
            try:
                tenant_id = int(data_object["client_reference_id"])
            except (TypeError, ValueError):
                tenant_id = None
        if sub_id:
            stripe = get_stripe()
            subscription = stripe.Subscription.retrieve(sub_id)
            tenant = sync_tenant_from_subscription(
                session, subscription=dict(subscription), tenant_id=tenant_id
            )
            summary["tenantId"] = tenant.tenant_id if tenant else None
        elif tenant_id:
            tenant = session.get(Tenant, tenant_id)
            if tenant:
                customer = data_object.get("customer")
                if customer:
                    tenant.stripe_customer_id = customer
                tenant.billing_status = "active"
                if meta.get("plan_tier"):
                    apply_plan_to_tenant(tenant, meta["plan_tier"])
                session.add(tenant)
                summary["tenantId"] = tenant.tenant_id

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        tenant = sync_tenant_from_subscription(session, subscription=data_object)
        if event_type == "customer.subscription.deleted" and tenant:
            tenant.billing_status = "canceled"
            tenant.stripe_subscription_id = None
            session.add(tenant)
        summary["tenantId"] = tenant.tenant_id if tenant else None

    elif event_type == "invoice.payment_failed":
        tenant = _find_tenant_for_invoice(session, data_object)
        if tenant:
            tenant.billing_status = "past_due"
            tenant.updated_at = datetime.utcnow()
            session.add(tenant)
            summary["tenantId"] = tenant.tenant_id

    elif event_type == "invoice.paid":
        tenant = _find_tenant_for_invoice(session, data_object)
        if tenant:
            # Prefer live subscription status when available
            sub_id = data_object.get("subscription")
            if isinstance(sub_id, dict):
                sub_id = sub_id.get("id")
            if sub_id:
                stripe = get_stripe()
                subscription = stripe.Subscription.retrieve(sub_id)
                sync_tenant_from_subscription(session, subscription=dict(subscription))
            else:
                tenant.billing_status = "active"
                tenant.updated_at = datetime.utcnow()
                session.add(tenant)
            summary["tenantId"] = tenant.tenant_id

    else:
        summary["ignored"] = True

    return summary


def construct_webhook_event(payload: bytes | str, sig_header: str | None) -> dict[str, Any]:
    secrets = require_stripe_configured()
    if not secrets.webhook_secret:
        raise AppError("Stripe webhook secret is not configured", 503, "STRIPE_NOT_CONFIGURED")
    if not sig_header:
        raise AppError("Missing Stripe-Signature header", 400, "STRIPE_SIGNATURE_MISSING")
    stripe = get_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload if isinstance(payload, (bytes, bytearray)) else payload.encode("utf-8"),
            sig_header=sig_header,
            secret=secrets.webhook_secret,
        )
    except Exception as exc:
        # Do not include payload or secret material in logs/messages.
        logger.warn("Stripe webhook signature verification failed", {"error_type": type(exc).__name__})
        raise AppError("Invalid Stripe signature", 400, "STRIPE_SIGNATURE_INVALID") from exc
    return dict(event)
