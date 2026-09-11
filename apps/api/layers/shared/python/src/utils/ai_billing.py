"""Hybrid AI plan catalog + quota / billing gate helpers (0009/0010/0011 + Razorpay INR)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from middleware.error_handler import AppError, ValidationError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

# USD list prices are canonical for Stripe. INR list prices are fixed product
# prices for Razorpay (not live FX) — see FEATURE-HYBRID-AI-BILLING.md / PRICING.md.
PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "starter": {
        "id": "starter",
        "label": "Starter",
        "monthly_usd": 49,
        "monthly_inr": 4099,
        "quota": 40,
        "byok_allowed": False,
    },
    "growth": {
        "id": "growth",
        "label": "Growth",
        "monthly_usd": 149,
        "monthly_inr": 12499,
        "quota": 150,
        "byok_allowed": True,
    },
    "scale": {
        "id": "scale",
        "label": "Scale",
        "monthly_usd": 399,
        "monthly_inr": 33499,
        "quota": 500,
        "byok_allowed": True,
    },
    "agency": {
        "id": "agency",
        "label": "Agency",
        "monthly_usd": 399,
        "monthly_inr": 33499,
        "quota": 50,  # small platform trial; BYOK expected
        "byok_allowed": True,
    },
}

# Documented USD↔INR mapping (fixed product prices; ~₹83–84 / USD rounded for retail)
USD_INR_MAPPING_NOTE = (
    "starter $49→₹4,099; growth $149→₹12,499; scale/agency $399→₹33,499"
)

PLATFORM_SOFT_LOCK_STATUSES = frozenset(
    {"past_due", "unpaid", "canceled", "incomplete_expired"}
)
ACTIVE_SUBSCRIPTION_STATUSES = frozenset(
    {"active", "trialing", "past_due", "unpaid", "incomplete", "paused"}
)

BillingGateway = Literal["stripe", "razorpay"]


def current_usage_month(now: datetime | None = None) -> str:
    now = now or _utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def get_plan(tier: str | None) -> dict[str, Any]:
    key = (tier or "starter").strip().lower()
    if key not in PLAN_CATALOG:
        raise ValidationError(f"Unknown plan tier: {tier}")
    return PLAN_CATALOG[key]


def apply_plan_to_tenant(tenant: Any, tier: str) -> None:
    plan = get_plan(tier)
    tenant.plan_tier = plan["id"]
    tenant.ai_posts_quota_monthly = int(plan["quota"])
    tenant.updated_at = _utcnow()


def reset_quota_month_if_needed(tenant: Any, now: datetime | None = None) -> None:
    month = current_usage_month(now)
    if getattr(tenant, "ai_usage_month", None) != month:
        tenant.ai_usage_month = month
        tenant.ai_posts_used_month = 0


def is_byok_mode(tenant: Any) -> bool:
    return (getattr(tenant, "ai_billing_mode", None) or "platform").strip().lower() == "byok"


def assert_platform_billing_ok(tenant: Any) -> None:
    """Soft-lock platform-mode AI when subscription is past-due / unpaid.

    BYOK tenants are never blocked by payment gateway status.
    """
    if is_byok_mode(tenant):
        return
    status = (getattr(tenant, "billing_status", None) or "none").strip().lower()
    if status in PLATFORM_SOFT_LOCK_STATUSES:
        raise AppError(
            "Your subscription payment needs attention. Update billing to continue "
            "using platform AI, or switch to BYOK.",
            402,
            "billing_required",
        )


def ensure_monthly_quota(tenant: Any, units: int = 1) -> None:
    """Consume platform quota for billable generate actions. No-op for BYOK."""
    if units < 1:
        raise ValidationError("units must be >= 1")
    if is_byok_mode(tenant):
        return
    assert_platform_billing_ok(tenant)
    reset_quota_month_if_needed(tenant)
    used = int(getattr(tenant, "ai_posts_used_month", 0) or 0)
    limit = int(getattr(tenant, "ai_posts_quota_monthly", 0) or 0)
    if used + units > limit:
        raise AppError(
            f"Monthly AI quota exceeded ({used}/{limit}). Upgrade your plan or switch to BYOK.",
            402,
            "QUOTA_EXCEEDED",
        )
    tenant.ai_posts_used_month = used + units


def catalog_public() -> list[dict[str, Any]]:
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "monthlyUsd": p["monthly_usd"],
            "monthlyInr": p["monthly_inr"],
            "quota": p["quota"],
            "byokAllowed": p["byok_allowed"],
            "display": {
                "usd": f"${p['monthly_usd']:,.0f}/mo",
                "inr": f"₹{p['monthly_inr']:,.0f}/mo",
            },
        }
        for p in PLAN_CATALOG.values()
    ]


def gateway_has_active_subscription(tenant: Any, gateway: BillingGateway) -> bool:
    status = (getattr(tenant, "billing_status", None) or "none").strip().lower()
    if status not in ACTIVE_SUBSCRIPTION_STATUSES:
        return False
    active_gw = (getattr(tenant, "billing_gateway", None) or "").strip().lower()
    if gateway == "stripe":
        return bool(getattr(tenant, "stripe_subscription_id", None)) and active_gw in (
            "",
            "stripe",
        )
    if gateway == "razorpay":
        return bool(getattr(tenant, "razorpay_subscription_id", None)) and active_gw in (
            "",
            "razorpay",
        )
    return False


def assert_can_subscribe(tenant: Any, gateway: BillingGateway) -> None:
    """Prevent double billing across Stripe and Razorpay.

    Switching requires cancel-then-resubscribe (no concurrent active gateways).
    """
    other: BillingGateway = "razorpay" if gateway == "stripe" else "stripe"
    status = (getattr(tenant, "billing_status", None) or "none").strip().lower()
    active_gw = (getattr(tenant, "billing_gateway", None) or "").strip().lower()

    if status not in ACTIVE_SUBSCRIPTION_STATUSES and not (
        getattr(tenant, "stripe_subscription_id", None)
        or getattr(tenant, "razorpay_subscription_id", None)
    ):
        return

    # Same-gateway upgrade / change is allowed.
    if active_gw == gateway:
        return

    other_sub = (
        getattr(tenant, "razorpay_subscription_id", None)
        if other == "razorpay"
        else getattr(tenant, "stripe_subscription_id", None)
    )
    blocks = (
        (active_gw == other and bool(other_sub))
        or (
            bool(other_sub)
            and status in ACTIVE_SUBSCRIPTION_STATUSES
            and active_gw in ("", other)
        )
        or gateway_has_active_subscription(tenant, other)
    )

    if blocks:
        raise ValidationError(
            f"This workspace already has an active {other} subscription. "
            f"Cancel it first, then subscribe with {gateway}."
        )


def preferred_gateway_for_currency(currency: str | None) -> BillingGateway:
    cur = (currency or "usd").strip().lower()
    if cur in ("inr", "₹", "rs", "rupee", "rupees"):
        return "razorpay"
    return "stripe"
