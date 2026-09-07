"""Hybrid AI billing — plan catalog and safe public serializers (no API secrets)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_PLAN = "starter"
DEFAULT_AI_BILLING_MODE = "platform"


@dataclass(frozen=True)
class PlanLimits:
    id: str
    label: str
    monthly_usd: float
    monthly_inr: float
    ai_posts_quota_monthly: int
    byok_allowed: bool
    byok_required: bool = False
    overage_usd_per_block: float | None = None
    overage_posts_per_block: int | None = None
    description: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "monthlyUsd": self.monthly_usd,
            "monthlyInr": self.monthly_inr,
            "quota": self.ai_posts_quota_monthly,
            "byokAllowed": self.byok_allowed,
            "byokRequired": self.byok_required,
            "overage": (
                {
                    "usdPerBlock": self.overage_usd_per_block,
                    "postsPerBlock": self.overage_posts_per_block,
                }
                if self.overage_usd_per_block is not None
                and self.overage_posts_per_block is not None
                else None
            ),
            "description": self.description,
            "display": {
                "usd": f"${self.monthly_usd:,.0f}/mo",
                "inr": f"₹{self.monthly_inr:,.0f}/mo",
            },
        }


PLAN_CATALOG: dict[str, PlanLimits] = {
    "starter": PlanLimits(
        id="starter",
        label="Starter",
        monthly_usd=49,
        monthly_inr=4099,
        ai_posts_quota_monthly=40,
        byok_allowed=False,
        overage_usd_per_block=15,
        overage_posts_per_block=25,
        description="Platform-included AI with a starter monthly post quota.",
    ),
    "growth": PlanLimits(
        id="growth",
        label="Growth",
        monthly_usd=149,
        monthly_inr=12499,
        ai_posts_quota_monthly=150,
        byok_allowed=True,
        overage_usd_per_block=40,
        overage_posts_per_block=100,
        description="Higher quota; BYOK included for Growth+.",
    ),
    "scale": PlanLimits(
        id="scale",
        label="Scale",
        monthly_usd=399,
        monthly_inr=33499,
        ai_posts_quota_monthly=500,
        byok_allowed=True,
        description="Large platform quota with BYOK unlock.",
    ),
    "agency": PlanLimits(
        id="agency",
        label="Agency",
        monthly_usd=399,
        monthly_inr=33499,
        ai_posts_quota_monthly=0,
        byok_allowed=True,
        byok_required=True,
        description="BYOK required — platform AI COGS not included (0 platform quota).",
    ),
}


def get_plan(plan_id: str | None) -> PlanLimits:
    key = (plan_id or DEFAULT_PLAN).strip().lower()
    return PLAN_CATALOG.get(key) or PLAN_CATALOG[DEFAULT_PLAN]


def list_plans_public() -> list[dict[str, Any]]:
    return [p.public_dict() for p in PLAN_CATALOG.values()]


def default_quota_for_plan(plan_id: str | None = None) -> int:
    return get_plan(plan_id).ai_posts_quota_monthly


def apply_billing_defaults(tenant: Any, *, plan: str | None = None, mode: str | None = None) -> None:
    plan_id = (plan or getattr(tenant, "plan", None) or DEFAULT_PLAN).strip().lower()
    if plan_id not in PLAN_CATALOG:
        plan_id = DEFAULT_PLAN
    mode_id = (
        mode or getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE
    ).strip().lower()
    if mode_id not in ("platform", "byok"):
        mode_id = DEFAULT_AI_BILLING_MODE
    limits = get_plan(plan_id)
    tenant.plan = plan_id
    tenant.ai_billing_mode = mode_id
    tenant.ai_posts_quota_monthly = limits.ai_posts_quota_monthly
    tenant.ai_posts_used_month = int(getattr(tenant, "ai_posts_used_month", None) or 0)


_SECRET_KEY_NAMES = frozenset(
    {
        "secret",
        "token",
        "api_key",
        "apikey",
        "openai_api_key",
        "openaiapikey",
        "gemini_api_key",
        "geminiapikey",
        "ai_secret_arn",
        "aisecretarn",
        "client_secret",
        "clientsecret",
        "access_token",
        "refresh_token",
        "authorization",
        "password",
    }
)


def _is_secret_key(name: str) -> bool:
    compact = name.lower().replace("-", "_")
    nosep = compact.replace("_", "")
    if compact in _SECRET_KEY_NAMES or nosep in _SECRET_KEY_NAMES:
        return True
    if "customer_id" in compact:
        return False
    if compact.endswith("_secret") or "secret_arn" in compact:
        return True
    if "api_key" in compact or compact.endswith("apikey"):
        return True
    return False


def redact_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _is_secret_key(key):
                continue
            if isinstance(v, str) and (v.startswith("sk-") or v.startswith("AIza")):
                continue
            out[key] = redact_secrets(v)
        return out
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(v) for v in value)
    return value


def tenant_billing_public(tenant: Any) -> dict[str, Any]:
    plan_id = getattr(tenant, "plan", None) or DEFAULT_PLAN
    mode = getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE
    limits = get_plan(plan_id)
    quota_limit = getattr(tenant, "ai_posts_quota_monthly", None)
    if quota_limit is None:
        quota_limit = limits.ai_posts_quota_monthly
    used = getattr(tenant, "ai_posts_used_month", None) or 0
    month = getattr(tenant, "ai_usage_month", None)
    payload = {
        "plan": plan_id,
        "planTier": plan_id,
        "aiBillingMode": mode,
        "byokAllowed": limits.byok_allowed,
        "byokRequired": limits.byok_required,
        "byokConfigured": bool(getattr(tenant, "ai_secret_arn", None)),
        "quota": {
            "monthlyLimit": int(quota_limit),
            "usedThisMonth": int(used),
            "month": month,
            "remaining": max(0, int(quota_limit) - int(used)),
        },
        "plans": list_plans_public(),
    }
    return redact_secrets(payload)
