"""Credential resolution, platform quota enforcement, and AiUsageEvent recording."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from billing import DEFAULT_AI_BILLING_MODE, DEFAULT_PLAN, get_plan
from billing.ai_secrets import get_platform_ai_secrets, get_tenant_ai_secrets
from billing.schema import ensure_tenant_billing_schema
from middleware.error_handler import AppError


@dataclass
class ResolvedAiCredentials:
    mode: str  # platform | byok
    openai_api_key: str | None
    gemini_api_key: str | None
    source: str  # platform | byok | env | stub
    provider_hint: str | None = None

    def as_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.openai_api_key:
            out["OPENAI_API_KEY"] = self.openai_api_key
        if self.gemini_api_key:
            out["GEMINI_API_KEY"] = self.gemini_api_key
        return out


class QuotaExceededError(AppError):
    """HTTP 402 with upgrade payload for Review / billing UI."""

    def __init__(self, message: str, *, plan: dict, usage: dict, status_code: int = 402):
        super().__init__(message, status_code, "QUOTA_EXCEEDED")
        self.upgrade = True
        self.plan = plan
        self.usage = usage


def current_usage_month(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def _is_production() -> bool:
    app_env = (os.environ.get("APP_ENV") or "").strip().lower()
    if app_env in ("production", "prod"):
        return True
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    return env in ("production", "prod")


def _is_stub_provider(name: str | None = None) -> bool:
    resolved = (name or os.environ.get("AI_PROVIDER") or "").lower().strip()
    return resolved == "stub"


def should_record_stub_usage() -> bool:
    """Stub usage events outside production (tests/dev); disable with RECORD_STUB_USAGE=false."""
    flag = (os.environ.get("RECORD_STUB_USAGE") or "true").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return not _is_production()


def resolve_ai_credentials(tenant: Any, *, preferred_provider: str | None = None) -> ResolvedAiCredentials:
    """Platform ΓåÆ AI_SECRET_ID/env; BYOK ΓåÆ tenant-stored keys; stub ΓåÆ empty keys."""
    ensure_tenant_billing_schema()
    mode = (getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE).strip().lower()
    if mode not in ("platform", "byok"):
        mode = DEFAULT_AI_BILLING_MODE

    if _is_stub_provider(preferred_provider):
        return ResolvedAiCredentials(
            mode=mode,
            openai_api_key=None,
            gemini_api_key=None,
            source="stub",
            provider_hint="stub",
        )

    if mode == "byok":
        plan = get_plan(getattr(tenant, "plan", None))
        if not plan.byok_allowed:
            raise AppError(
                f"Plan '{plan.id}' does not allow bring-your-own-keys. Upgrade to Growth+.",
                403,
                "BYOK_NOT_ALLOWED",
            )
        keys = get_tenant_ai_secrets(
            int(tenant.tenant_id),
            getattr(tenant, "ai_secret_arn", None),
        )
        openai_key = (keys.get("OPENAI_API_KEY") or "").strip() or None
        gemini_key = (keys.get("GEMINI_API_KEY") or "").strip() or None
        if not openai_key and not gemini_key:
            raise AppError(
                "BYOK mode requires at least one configured AI key.",
                400,
                "BYOK_KEYS_MISSING",
            )
        return ResolvedAiCredentials(
            mode="byok",
            openai_api_key=openai_key,
            gemini_api_key=gemini_key,
            source="byok",
            provider_hint=preferred_provider,
        )

    platform = get_platform_ai_secrets()
    return ResolvedAiCredentials(
        mode="platform",
        openai_api_key=(platform.get("OPENAI_API_KEY") or "").strip() or None,
        gemini_api_key=(platform.get("GEMINI_API_KEY") or "").strip() or None,
        source="platform" if (os.environ.get("AI_SECRET_ID") or "").strip() else "env",
        provider_hint=(platform.get("AI_PROVIDER") or preferred_provider),
    )


def _quota_snapshot(tenant: Any) -> tuple[int, int, str]:
    """Return (limit, used, month) after rolling the month window if needed."""
    month = current_usage_month()
    stored_month = getattr(tenant, "ai_usage_month", None)
    if stored_month != month:
        tenant.ai_usage_month = month
        tenant.ai_posts_used_month = 0
    limit = getattr(tenant, "ai_posts_quota_monthly", None)
    if limit is None:
        limit = get_plan(getattr(tenant, "plan", None)).ai_posts_quota_monthly
    used = int(getattr(tenant, "ai_posts_used_month", None) or 0)
    return int(limit), used, month


def usage_public(tenant: Any) -> dict[str, Any]:
    limit, used, month = _quota_snapshot(tenant)
    return {
        "monthlyLimit": limit,
        "usedThisMonth": used,
        "month": month,
        "remaining": max(0, limit - used),
    }


def plan_public(tenant: Any) -> dict[str, Any]:
    plan_id = getattr(tenant, "plan", None) or DEFAULT_PLAN
    return get_plan(plan_id).public_dict()


def assert_platform_quota(tenant: Any, units: int) -> None:
    """Raise QuotaExceededError when platform mode cannot cover `units`."""
    units = max(0, int(units))
    if units <= 0:
        return
    mode = (getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE).strip().lower()
    if mode != "platform":
        return
    limit, used, _month = _quota_snapshot(tenant)
    if used + units > limit:
        raise QuotaExceededError(
            "Monthly AI quota exceeded. Upgrade your plan or switch to BYOK.",
            plan=plan_public(tenant),
            usage=usage_public(tenant),
            status_code=402,
        )


def assert_and_consume_quota(session, tenant: Any, units: int) -> None:
    """
    Platform-only: re-check remaining capacity then increment counters.
    Call after successful AI work. No-op for BYOK.
    """
    units = max(0, int(units))
    if units <= 0:
        return
    mode = (getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE).strip().lower()
    if mode != "platform":
        return
    assert_platform_quota(tenant, units)
    _limit, used, month = _quota_snapshot(tenant)
    tenant.ai_usage_month = month
    tenant.ai_posts_used_month = used + units
    tenant.updated_at = datetime.utcnow()
    session.add(tenant)


def record_usage_event(
    session,
    *,
    tenant: Any,
    kind: str,
    units: int,
    model: str | None = None,
    meta: dict | None = None,
    billing_mode: str | None = None,
    provider: str | None = None,
) -> Any:
    """Always insert a tenant-scoped AiUsageEvent (no secrets in meta)."""
    from database.models import AiUsageEvent
    from billing import redact_secrets

    ensure_tenant_billing_schema()
    mode = billing_mode or getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE
    safe_meta = redact_secrets(
        {
            **(meta or {}),
            "billingMode": mode,
            "provider": provider,
            "plan": getattr(tenant, "plan", None) or DEFAULT_PLAN,
        }
    )
    event = AiUsageEvent(
        tenant_id=int(tenant.tenant_id),
        kind=kind,
        units=max(0, int(units)),
        model=model,
        meta_json=json.dumps(safe_meta),
    )
    session.add(event)
    return event


def meter_ai_success(
    session,
    *,
    tenant: Any,
    kind: str,
    units: int,
    model: str | None = None,
    provider: str | None = None,
    meta: dict | None = None,
    creds: ResolvedAiCredentials | None = None,
) -> None:
    """
    After successful AI:
    - platform ΓåÆ assert_and_consume_quota + usage event
    - byok ΓåÆ usage event only (no platform quota)
    - stub ΓåÆ optional usage event outside production
    """
    mode = (getattr(tenant, "ai_billing_mode", None) or DEFAULT_AI_BILLING_MODE).strip().lower()
    is_stub = (creds and creds.source == "stub") or _is_stub_provider(provider)

    if is_stub and not should_record_stub_usage():
        return

    if mode == "platform" and not is_stub:
        assert_and_consume_quota(session, tenant, units)
    elif mode == "platform" and is_stub:
        # Enforce + consume in stub too so local/tests exercise metering
        assert_and_consume_quota(session, tenant, units)

    record_usage_event(
        session,
        tenant=tenant,
        kind=kind,
        units=units,
        model=model,
        billing_mode=mode,
        provider=provider or (creds.source if creds else None),
        meta=meta,
    )


def list_usage_events_for_tenant(session, tenant_id: int, *, limit: int = 50) -> list[dict]:
    from database.models import AiUsageEvent
    from sqlmodel import select

    ensure_tenant_billing_schema()
    rows = session.exec(
        select(AiUsageEvent)
        .where(AiUsageEvent.tenant_id == tenant_id)
        .order_by(AiUsageEvent.created_at.desc())
        .limit(max(1, min(int(limit), 200)))
    ).all()
    out = []
    for r in rows:
        try:
            meta = json.loads(r.meta_json or "{}")
        except Exception:
            meta = {}
        out.append(
            {
                "eventId": r.event_id,
                "tenantId": r.tenant_id,
                "kind": r.kind,
                "units": r.units,
                "model": r.model,
                "meta": meta,
                "createdAt": r.created_at.isoformat() + "Z" if r.created_at else None,
            }
        )
    return out
