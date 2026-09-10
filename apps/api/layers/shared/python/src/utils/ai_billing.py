"""Hybrid AI plan catalog + quota / billing gate helpers (0009/0010/0011)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from middleware.error_handler import AppError, ValidationError

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "starter": {
        "id": "starter",
        "label": "Starter",
        "monthly_usd": 49,
        "quota": 40,
        "byok_allowed": False,
    },
    "growth": {
        "id": "growth",
        "label": "Growth",
        "monthly_usd": 149,
        "quota": 150,
        "byok_allowed": True,
    },
    "scale": {
        "id": "scale",
        "label": "Scale",
        "monthly_usd": 399,
        "quota": 500,
        "byok_allowed": True,
    },
    "agency": {
        "id": "agency",
        "label": "Agency",
        "monthly_usd": 399,
        "quota": 50,  # small platform trial; BYOK expected
        "byok_allowed": True,
    },
}

PLATFORM_SOFT_LOCK_STATUSES = frozenset({"past_due", "unpaid", "canceled", "incomplete_expired"})


def current_usage_month(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
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
    tenant.updated_at = datetime.utcnow()


def reset_quota_month_if_needed(tenant: Any, now: datetime | None = None) -> None:
    month = current_usage_month(now)
    if getattr(tenant, "ai_usage_month", None) != month:
        tenant.ai_usage_month = month
        tenant.ai_posts_used_month = 0


def is_byok_mode(tenant: Any) -> bool:
    return (getattr(tenant, "ai_billing_mode", None) or "platform").strip().lower() == "byok"


def assert_platform_billing_ok(tenant: Any) -> None:
    """Soft-lock platform-mode AI when Stripe subscription is past-due / unpaid.

    BYOK tenants are never blocked by Stripe payment status.
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
            "quota": p["quota"],
            "byokAllowed": p["byok_allowed"],
        }
        for p in PLAN_CATALOG.values()
    ]
