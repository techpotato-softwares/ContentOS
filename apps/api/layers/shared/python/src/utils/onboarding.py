"""First-run onboarding state persisted on Tenant.onboarding_json."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlmodel import select

from database.models import ContentPost, SocialAccount, Tenant
from middleware.error_handler import ValidationError

ONBOARDING_STEPS = ("linkedin", "training", "generate", "publish")
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"


def default_onboarding() -> dict[str, Any]:
    return {
        "version": 1,
        "status": STATUS_PENDING,
        "steps": {s: False for s in ONBOARDING_STEPS},
        "skippedAt": None,
        "completedAt": None,
        "updatedAt": None,
    }


def ensure_onboarding_schema() -> None:
    """Idempotent column for existing DBs (Alembic-friendly create_all path)."""
    try:
        from sqlalchemy import text
        from database import get_engine

        with get_engine().begin() as conn:
            try:
                conn.execute(
                    text(
                        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS onboarding_json TEXT DEFAULT '{}'"
                    )
                )
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE tenants ADD COLUMN onboarding_json TEXT"))
                except Exception:
                    pass
    except Exception:
        pass


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def normalize_onboarding(raw: dict | None) -> dict[str, Any]:
    base = default_onboarding()
    if not isinstance(raw, dict):
        return base
    status = raw.get("status") or STATUS_PENDING
    if status not in (STATUS_PENDING, STATUS_COMPLETED, STATUS_SKIPPED):
        status = STATUS_PENDING
    steps_in = raw.get("steps") if isinstance(raw.get("steps"), dict) else {}
    steps = {s: bool(steps_in.get(s)) for s in ONBOARDING_STEPS}
    return {
        "version": int(raw.get("version") or 1),
        "status": status,
        "steps": steps,
        "skippedAt": raw.get("skippedAt"),
        "completedAt": raw.get("completedAt"),
        "updatedAt": raw.get("updatedAt"),
    }


def parse_onboarding(tenant: Tenant) -> dict[str, Any]:
    raw_text = getattr(tenant, "onboarding_json", None) or ""
    if not str(raw_text).strip() or str(raw_text).strip() == "{}":
        return default_onboarding()
    try:
        return normalize_onboarding(json.loads(raw_text))
    except Exception:
        return default_onboarding()


def save_onboarding(session, tenant: Tenant, state: dict[str, Any]) -> dict[str, Any]:
    state = normalize_onboarding(state)
    state["updatedAt"] = _utcnow_iso()
    tenant.onboarding_json = json.dumps(state)
    tenant.updated_at = datetime.utcnow()
    session.add(tenant)
    return state


def public_onboarding(state: dict[str, Any]) -> dict[str, Any]:
    """API-facing camelCase payload."""
    s = normalize_onboarding(state)
    return {
        "version": s["version"],
        "status": s["status"],
        "steps": {
            "linkedin": bool(s["steps"].get("linkedin")),
            "training": bool(s["steps"].get("training")),
            "generate": bool(s["steps"].get("generate")),
            "publish": bool(s["steps"].get("publish")),
        },
        "skippedAt": s.get("skippedAt"),
        "completedAt": s.get("completedAt"),
        "updatedAt": s.get("updatedAt"),
        "visible": s["status"] == STATUS_PENDING,
        "stepOrder": list(ONBOARDING_STEPS),
    }


def _has_linkedin(session, tenant_id: int) -> bool:
    row = session.exec(
        select(SocialAccount).where(
            SocialAccount.tenant_id == tenant_id,
            SocialAccount.platform == "linkedin",
            SocialAccount.is_active == True,  # noqa: E712
        )
    ).first()
    return bool(row and (row.author_urn or row.token_payload_encrypted))


def _has_posts(session, tenant_id: int) -> bool:
    return (
        session.exec(
            select(ContentPost).where(ContentPost.tenant_id == tenant_id)
        ).first()
        is not None
    )


def _has_published(session, tenant_id: int) -> bool:
    return (
        session.exec(
            select(ContentPost).where(
                ContentPost.tenant_id == tenant_id,
                ContentPost.status == "published",
            )
        ).first()
        is not None
    )


def apply_fact_sync(session, tenant: Tenant, state: dict[str, Any]) -> dict[str, Any]:
    """Mark steps true when backend facts prove completion (does not un-skip)."""
    state = normalize_onboarding(state)
    if state["status"] in (STATUS_COMPLETED, STATUS_SKIPPED):
        return state
    tid = int(tenant.tenant_id)  # type: ignore[arg-type]
    if _has_linkedin(session, tid):
        state["steps"]["linkedin"] = True
    if (tenant.context_pack_version or 0) > 0:
        state["steps"]["training"] = True
    if _has_posts(session, tid):
        state["steps"]["generate"] = True
    if _has_published(session, tid):
        state["steps"]["publish"] = True
        state["status"] = STATUS_COMPLETED
        state["completedAt"] = state.get("completedAt") or _utcnow_iso()
    elif all(state["steps"].get(s) for s in ONBOARDING_STEPS):
        state["status"] = STATUS_COMPLETED
        state["completedAt"] = state.get("completedAt") or _utcnow_iso()
    return state


def get_or_init_onboarding(session, tenant: Tenant) -> dict[str, Any]:
    """Load state; initialize for new tenants; auto-complete legacy tenants with publishes."""
    ensure_onboarding_schema()
    raw_text = getattr(tenant, "onboarding_json", None) or ""
    uninitialized = not str(raw_text).strip() or str(raw_text).strip() == "{}"
    if uninitialized:
        if _has_published(session, int(tenant.tenant_id)):  # type: ignore[arg-type]
            state = default_onboarding()
            for s in ONBOARDING_STEPS:
                state["steps"][s] = True
            state["status"] = STATUS_COMPLETED
            state["completedAt"] = _utcnow_iso()
        else:
            state = default_onboarding()
        return save_onboarding(session, tenant, state)

    state = parse_onboarding(tenant)
    if state["status"] == STATUS_PENDING:
        synced = apply_fact_sync(session, tenant, state)
        if synced != state:
            return save_onboarding(session, tenant, synced)
    return state


def mark_onboarding_step(
    session,
    *,
    tenant_id: int,
    step: str,
) -> dict[str, Any] | None:
    """Mark a step complete after a successful backend action. No-op if skipped/done."""
    if step not in ONBOARDING_STEPS:
        raise ValidationError(f"Unknown onboarding step: {step}")
    ensure_onboarding_schema()
    tenant = session.get(Tenant, int(tenant_id))
    if not tenant:
        return None
    state = parse_onboarding(tenant)
    if state["status"] in (STATUS_COMPLETED, STATUS_SKIPPED):
        return state
    state["steps"][step] = True
    if step == "publish":
        state["status"] = STATUS_COMPLETED
        state["completedAt"] = _utcnow_iso()
    elif all(state["steps"].get(s) for s in ONBOARDING_STEPS):
        state["status"] = STATUS_COMPLETED
        state["completedAt"] = _utcnow_iso()
    return save_onboarding(session, tenant, state)


def skip_onboarding(session, tenant: Tenant) -> dict[str, Any]:
    state = parse_onboarding(tenant)
    if state["status"] == STATUS_COMPLETED:
        return state
    state["status"] = STATUS_SKIPPED
    state["skippedAt"] = _utcnow_iso()
    return save_onboarding(session, tenant, state)


def verify_step_complete(session, tenant: Tenant, step: str) -> bool:
    """True when backend facts show the step was actually done."""
    tid = int(tenant.tenant_id)  # type: ignore[arg-type]
    if step == "linkedin":
        return _has_linkedin(session, tid)
    if step == "training":
        return (tenant.context_pack_version or 0) > 0
    if step == "generate":
        return _has_posts(session, tid)
    if step == "publish":
        return _has_published(session, tid)
    raise ValidationError(f"Unknown onboarding step: {step}")
