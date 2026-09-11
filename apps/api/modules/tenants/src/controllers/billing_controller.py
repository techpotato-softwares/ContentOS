"""Stripe + Razorpay billing: checkout, portal, payment links, signed webhooks."""
from __future__ import annotations

from database import get_session
from database.models import Tenant
from decorators import Controller, Get, Post
from decorators.auth_decorators import ApiPublic, RequireModule, RequirePermission
from middleware.error_handler import (
    AppError,
    NotFoundError,
    ValidationError,
    create_success_response,
)
from sqlalchemy.exc import IntegrityError
from utils.ai_billing import (
    PLAN_CATALOG,
    catalog_public,
    get_plan,
    is_byok_mode,
    preferred_gateway_for_currency,
)
from utils.logger import logger
from utils.razorpay_billing import (
    cancel_subscription as cancel_razorpay_subscription,
)
from utils.razorpay_billing import (
    create_payment_link as create_razorpay_payment_link,
)
from utils.razorpay_billing import (
    create_subscription as create_razorpay_subscription,
)
from utils.razorpay_billing import (
    process_razorpay_event,
)
from utils.razorpay_billing import (
    verify_webhook_signature as verify_razorpay_webhook,
)
from utils.stripe_billing import (
    construct_webhook_event,
    create_checkout_session,
    create_portal_session,
    process_stripe_event,
)
from utils.tenant import require_user, resolve_tenant_id, write_audit
from utils.tenant_billing_schema import ensure_tenant_billing_columns


def _header(event: dict | None, name: str) -> str | None:
    if not event:
        return None
    headers = event.get("headers") or {}
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


def _query(event: dict | None, name: str) -> str | None:
    if not event:
        return None
    params = event.get("queryStringParameters") or {}
    return params.get(name)


@Controller(path="/api", lambda_name="tenants")
class BillingController:
    @Get("/billing/plans")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants", "training:manage")
    def list_plans(self, user=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        return create_success_response({"plans": catalog_public()})

    @Get("/billing/summary")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants", "training:manage")
    def billing_summary(self, user=None, event=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        currency = (_query(event, "currency") or "usd").strip().lower()
        preferred = preferred_gateway_for_currency(currency)
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            plan = get_plan(tenant.plan_tier or "starter")
            active_gw = (tenant.billing_gateway or None)
            return create_success_response(
                {
                    "planTier": tenant.plan_tier or "starter",
                    "planLabel": plan["label"],
                    "monthlyUsd": plan["monthly_usd"],
                    "monthlyInr": plan["monthly_inr"],
                    "aiBillingMode": tenant.ai_billing_mode or "platform",
                    "byok": is_byok_mode(tenant),
                    "byokAllowed": bool(plan["byok_allowed"]),
                    "billingStatus": tenant.billing_status or "none",
                    "billingGateway": active_gw,
                    "preferredCurrency": "inr" if preferred == "razorpay" else "usd",
                    "preferredGateway": preferred,
                    "hasStripeCustomer": bool(tenant.stripe_customer_id),
                    "hasStripeSubscription": bool(tenant.stripe_subscription_id),
                    "hasRazorpayCustomer": bool(tenant.razorpay_customer_id),
                    "hasRazorpaySubscription": bool(tenant.razorpay_subscription_id),
                    "hasSubscription": bool(
                        tenant.stripe_subscription_id or tenant.razorpay_subscription_id
                    ),
                    "quota": {
                        "used": tenant.ai_posts_used_month or 0,
                        "limit": tenant.ai_posts_quota_monthly or plan["quota"],
                        "month": tenant.ai_usage_month,
                    },
                    "plans": catalog_public(),
                }
            )

    @Post("/billing/checkout-session")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def checkout_session(self, data: dict, user=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        data = data or {}
        plan_tier = (data.get("planTier") or data.get("plan") or "").strip().lower()
        if plan_tier not in PLAN_CATALOG:
            raise ValidationError("planTier must be one of: starter, growth, scale, agency")
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            result = create_checkout_session(
                session,
                tenant=tenant,
                plan_tier=plan_tier,
                customer_email=user.get("email"),
                success_url=data.get("successUrl"),
                cancel_url=data.get("cancelUrl"),
            )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="billing.checkout_session",
                resource_type="tenant",
                resource_id=str(tid),
                detail=f"plan={plan_tier};gateway=stripe",
            )
            session.commit()
            return create_success_response(result)

    @Post("/billing/portal-session")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def portal_session(self, data: dict | None = None, user=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            result = create_portal_session(session, tenant=tenant)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="billing.portal_session",
                resource_type="tenant",
                resource_id=str(tid),
                detail="portal",
            )
            session.commit()
            return create_success_response(result)

    @Post("/billing/razorpay/subscription")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def razorpay_subscription(self, data: dict, user=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        data = data or {}
        plan_tier = (data.get("planTier") or data.get("plan") or "").strip().lower()
        if plan_tier not in PLAN_CATALOG:
            raise ValidationError("planTier must be one of: starter, growth, scale, agency")
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            result = create_razorpay_subscription(
                session,
                tenant=tenant,
                plan_tier=plan_tier,
                customer_email=user.get("email"),
            )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="billing.razorpay_subscription",
                resource_type="tenant",
                resource_id=str(tid),
                detail=f"plan={plan_tier}",
            )
            session.commit()
            return create_success_response(result)

    @Post("/billing/razorpay/payment-link")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def razorpay_payment_link(self, data: dict, user=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        data = data or {}
        plan_tier = (data.get("planTier") or data.get("plan") or "").strip().lower()
        if plan_tier not in PLAN_CATALOG:
            raise ValidationError("planTier must be one of: starter, growth, scale, agency")
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            result = create_razorpay_payment_link(
                session,
                tenant=tenant,
                plan_tier=plan_tier,
                customer_email=user.get("email"),
                success_url=data.get("successUrl"),
            )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="billing.razorpay_payment_link",
                resource_type="tenant",
                resource_id=str(tid),
                detail=f"plan={plan_tier}",
            )
            session.commit()
            return create_success_response(result)

    @Post("/billing/razorpay/cancel")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def razorpay_cancel(self, data: dict | None = None, user=None):
        user = require_user(user)
        ensure_tenant_billing_columns()
        data = data or {}
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            result = cancel_razorpay_subscription(
                session,
                tenant=tenant,
                cancel_at_cycle_end=bool(data.get("cancelAtCycleEnd")),
            )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="billing.razorpay_cancel",
                resource_type="tenant",
                resource_id=str(tid),
                detail="cancel",
            )
            session.commit()
            return create_success_response(result)

    @Post("/billing/webhook")
    @ApiPublic()
    def stripe_webhook(self, event=None):
        """Stripe signed webhook. Uses raw body from the Lambda/API Gateway event."""
        ensure_tenant_billing_columns()
        raw = (event or {}).get("body")
        if raw is None:
            raise ValidationError("Empty webhook body")
        if (event or {}).get("isBase64Encoded"):
            import base64

            payload = base64.b64decode(raw)
        else:
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw

        sig = _header(event, "stripe-signature")
        stripe_event = construct_webhook_event(payload, sig)

        with get_session() as session:
            try:
                summary = process_stripe_event(session, stripe_event)
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info(
                    "Stripe webhook duplicate (integrity)",
                    {"eventId": stripe_event.get("id"), "type": stripe_event.get("type")},
                )
                return create_success_response({"duplicate": True})
            except AppError:
                session.rollback()
                raise
            except Exception as exc:
                session.rollback()
                logger.error(
                    "Stripe webhook processing failed",
                    {"error_type": type(exc).__name__, "event_type": stripe_event.get("type")},
                )
                raise AppError("Webhook processing failed", 500, "STRIPE_WEBHOOK_FAILED") from exc

        return create_success_response(summary)

    @Post("/billing/razorpay/webhook")
    @ApiPublic()
    def razorpay_webhook(self, event=None):
        """Razorpay signed webhook. Uses raw body from the Lambda/API Gateway event."""
        ensure_tenant_billing_columns()
        raw = (event or {}).get("body")
        if raw is None:
            raise ValidationError("Empty webhook body")
        if (event or {}).get("isBase64Encoded"):
            import base64

            payload = base64.b64decode(raw)
        else:
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw

        sig = _header(event, "x-razorpay-signature")
        razorpay_event = verify_razorpay_webhook(payload, sig)

        with get_session() as session:
            try:
                summary = process_razorpay_event(session, razorpay_event)
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info(
                    "Razorpay webhook duplicate (integrity)",
                    {
                        "eventId": razorpay_event.get("id"),
                        "type": razorpay_event.get("event"),
                    },
                )
                return create_success_response({"duplicate": True})
            except AppError:
                session.rollback()
                raise
            except Exception as exc:
                session.rollback()
                logger.error(
                    "Razorpay webhook processing failed",
                    {
                        "error_type": type(exc).__name__,
                        "event_type": razorpay_event.get("event"),
                    },
                )
                raise AppError(
                    "Webhook processing failed", 500, "RAZORPAY_WEBHOOK_FAILED"
                ) from exc

        return create_success_response(summary)
