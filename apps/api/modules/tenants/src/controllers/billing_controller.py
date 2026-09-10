"""Stripe Billing: checkout, customer portal, signed webhooks."""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from decorators import Controller, Get, Post
from decorators.auth_decorators import ApiPublic, RequireModule, RequirePermission
from database import get_session
from database.models import Tenant
from middleware.error_handler import (
    AppError,
    NotFoundError,
    ValidationError,
    create_success_response,
)
from utils.ai_billing import PLAN_CATALOG, catalog_public, get_plan, is_byok_mode
from utils.stripe_billing import (
    construct_webhook_event,
    create_checkout_session,
    create_portal_session,
    process_stripe_event,
)
from utils.tenant import require_user, resolve_tenant_id, write_audit
from utils.tenant_billing_schema import ensure_tenant_billing_columns
from utils.logger import logger


def _header(event: dict | None, name: str) -> str | None:
    if not event:
        return None
    headers = event.get("headers") or {}
    # API Gateway may lowercase headers
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


@Controller(path="/api", lambda_name="tenants")
class BillingController:
    @Get("/billing/plans")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants", "training:manage")
    def list_plans(self, user=None):
        require_user(user)
        ensure_tenant_billing_columns()
        return create_success_response({"plans": catalog_public()})

    @Get("/billing/summary")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants", "training:manage")
    def billing_summary(self, user=None):
        require_user(user)
        ensure_tenant_billing_columns()
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            plan = get_plan(tenant.plan_tier or "starter")
            return create_success_response(
                {
                    "planTier": tenant.plan_tier or "starter",
                    "planLabel": plan["label"],
                    "monthlyUsd": plan["monthly_usd"],
                    "aiBillingMode": tenant.ai_billing_mode or "platform",
                    "byok": is_byok_mode(tenant),
                    "byokAllowed": bool(plan["byok_allowed"]),
                    "billingStatus": tenant.billing_status or "none",
                    "hasStripeCustomer": bool(tenant.stripe_customer_id),
                    "hasSubscription": bool(tenant.stripe_subscription_id),
                    "quota": {
                        "used": int(tenant.ai_posts_used_month or 0),
                        "limit": int(tenant.ai_posts_quota_monthly or plan["quota"]),
                        "month": tenant.ai_usage_month,
                    },
                    "plans": catalog_public(),
                }
            )

    @Post("/billing/checkout-session")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def checkout_session(self, data: dict, user=None):
        require_user(user)
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
                detail=f"plan={plan_tier}",
            )
            session.commit()
            return create_success_response(result)

    @Post("/billing/portal-session")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def portal_session(self, data: dict = None, user=None):
        require_user(user)
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
                # Concurrent duplicate delivery — treat as success (idempotent).
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
