"""Tenant first-run onboarding state helpers.

Persisted on ``Tenant.onboarding_json``. Steps mirror the product wizard:
Connect LinkedIn → Train Brand → Generate → Review → First Publish.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import select

ONBOARDING_VERSION = 1
STEP_KEYS = ("linkedin", "training", "generate", "review", "publish")


def ensure_onboarding_schema(session=None) -> None:
    """Idempotent ADD COLUMN for local/dev DBs that skip Alembic.

    Uses a separate engine transaction (same pattern as ``ensure_auth_schema``)
    so DDL is committed even if the request session later rolls back.
    """
    from database import get_engine
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with get_engine().begin() as conn:
            dialect = getattr(conn.dialect, "name", "") or ""
            if dialect == "sqlite":
                cols = {
                    r[1]
                    for r in conn.execute(text("PRAGMA table_info(tenants)")).fetchall()
                }
                if "onboarding_json" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE tenants ADD COLUMN onboarding_json TEXT DEFAULT '{}'"
                        )
                    )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "
                        "onboarding_json TEXT NOT NULL DEFAULT '{}'"
                    )
                )
    except SQLAlchemyError:
        # Best-effort for older SQLite / locked DBs; caller still gets a clear
        # UndefinedColumn if the column truly cannot be added.
        pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.replace(tzinfo=None).isoformat() + "Z"


def _parse_iso(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def default_onboarding_state() -> dict[str, Any]:
    steps = {
        key: {"status": "pending", "completedAt": None} for key in STEP_KEYS
    }
    return {
        "version": ONBOARDING_VERSION,
        "steps": steps,
        "skipped": False,
        "completedAt": None,
    }


def parse_onboarding(raw: str | None) -> dict[str, Any]:
    base = default_onboarding_state()
    if not raw or not raw.strip():
        return base
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return base
    if not isinstance(data, dict):
        return base

    steps_raw = data.get("steps")
    steps_in: dict[str, Any] = steps_raw if isinstance(steps_raw, dict) else {}
    steps: dict[str, Any] = {}
    for key in STEP_KEYS:
        step_raw = steps_in.get(key)
        src: dict[str, Any] = step_raw if isinstance(step_raw, dict) else {}
        # Backward-compatible bool flags: {"linkedin": true}
        if key in data and not isinstance(data.get(key), dict) and key not in steps_in:
            done = bool(data.get(key))
            steps[key] = {
                "status": "completed" if done else "pending",
                "completedAt": _iso(_utcnow()) if done else None,
            }
            continue
        status = str(src.get("status") or "pending").lower()
        if status not in ("pending", "completed"):
            status = "pending"
        completed_at = src.get("completedAt")
        if status == "completed" and not completed_at:
            completed_at = _iso(_utcnow())
        if status != "completed":
            completed_at = None
        steps[key] = {"status": status, "completedAt": completed_at}

    skipped = bool(data.get("skipped"))
    completed_at = data.get("completedAt")
    if skipped and not completed_at:
        completed_at = _iso(_utcnow())
    version_raw = data.get("version")
    try:
        version = int(version_raw) if version_raw is not None else ONBOARDING_VERSION
    except (TypeError, ValueError):
        version = ONBOARDING_VERSION
    return {
        "version": version,
        "steps": steps,
        "skipped": skipped,
        "completedAt": completed_at if isinstance(completed_at, str) or completed_at is None else None,
    }


def serialize_onboarding(state: dict[str, Any]) -> str:
    return json.dumps(parse_onboarding(json.dumps(state)), separators=(",", ":"))


def is_step_complete(state: dict[str, Any], step: str) -> bool:
    step_state = (state.get("steps") or {}).get(step) or {}
    return str(step_state.get("status")) == "completed"


def all_steps_complete(state: dict[str, Any]) -> bool:
    return all(is_step_complete(state, key) for key in STEP_KEYS)


def should_show_wizard(state: dict[str, Any]) -> bool:
    if state.get("skipped"):
        return False
    return not state.get("completedAt")


def public_onboarding(state: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_onboarding(json.dumps(state))
    return {
        **parsed,
        "showWizard": should_show_wizard(parsed),
        "allComplete": all_steps_complete(parsed),
    }


def mark_step_complete(state: dict[str, Any], step: str, *, at: datetime | None = None) -> dict[str, Any]:
    if step not in STEP_KEYS:
        return parse_onboarding(json.dumps(state))
    parsed = parse_onboarding(json.dumps(state))
    if is_step_complete(parsed, step):
        return parsed
    now = at or _utcnow()
    parsed["steps"][step] = {"status": "completed", "completedAt": _iso(now)}
    if (step == "publish" or all_steps_complete(parsed)) and not parsed.get(
        "completedAt"
    ):
        parsed["completedAt"] = _iso(now)
    return parsed


def mark_skipped(state: dict[str, Any], *, at: datetime | None = None) -> dict[str, Any]:
    parsed = parse_onboarding(json.dumps(state))
    now = at or _utcnow()
    parsed["skipped"] = True
    if not parsed.get("completedAt"):
        parsed["completedAt"] = _iso(now)
    return parsed


def apply_put_patch(state: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    """Apply user/API patch. Supports skip + explicit step status updates."""
    parsed = parse_onboarding(json.dumps(state))
    data = patch or {}
    if data.get("skipped") is True or data.get("skip") is True:
        return mark_skipped(parsed)

    # Re-open from Help/Settings: clear skip without wiping completed steps
    if data.get("skipped") is False and data.get("reopen") is True:
        parsed["skipped"] = False
        if not all_steps_complete(parsed):
            parsed["completedAt"] = None
        return parsed

    steps_patch = data.get("steps") if isinstance(data.get("steps"), dict) else {}
    for key in STEP_KEYS:
        if key in data and data[key] is True:
            parsed = mark_step_complete(parsed, key)
            continue
        src = steps_patch.get(key)
        if (
            isinstance(src, dict)
            and str(src.get("status") or "").lower() == "completed"
        ) or src is True:
            parsed = mark_step_complete(parsed, key)
    return parsed


def load_tenant_onboarding(tenant) -> dict[str, Any]:
    raw = getattr(tenant, "onboarding_json", None) or "{}"
    return parse_onboarding(raw)


def save_tenant_onboarding(session, tenant, state: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_onboarding(json.dumps(state))
    tenant.onboarding_json = serialize_onboarding(parsed)
    tenant.updated_at = _utcnow()
    session.add(tenant)
    return public_onboarding(parsed)


def complete_onboarding_step(session, tenant_id: int, step: str) -> dict[str, Any] | None:
    """Mark a step complete for a tenant. No-op if tenant missing or already done."""
    from database.models import Tenant

    if step not in STEP_KEYS or not tenant_id:
        return None
    ensure_onboarding_schema(session)
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return None
    state = load_tenant_onboarding(tenant)
    if state.get("skipped"):
        # Still record real progress so reopen shows accurate steps
        pass
    updated = mark_step_complete(state, step)
    if updated == state and is_step_complete(state, step):
        return public_onboarding(state)
    return save_tenant_onboarding(session, tenant, updated)


def sync_onboarding_from_reality(session, tenant) -> dict[str, Any]:
    """Hydrate step completion from existing LinkedIn/training/batch/publish data.

    Keeps returning/existing tenants from being forced through finished work.
    """
    from database.models import ContentPost, GenerationBatch, SocialAccount

    state = load_tenant_onboarding(tenant)
    tid = tenant.tenant_id
    changed = False

    # LinkedIn: any active account with author_urn
    accounts = session.exec(
        select(SocialAccount).where(
            SocialAccount.tenant_id == tid,
            SocialAccount.is_active == True,
        )
    ).all()
    if any(bool(a.author_urn) for a in accounts) and not is_step_complete(
        state, "linkedin"
    ):
        state = mark_step_complete(state, "linkedin")
        changed = True

    # Training: non-empty pack / version bump / non-default training_json
    training_raw = (tenant.training_json or "").strip()
    if (tenant.context_pack_version or 0) > 0 or (
        training_raw and training_raw not in ("{}", "")
    ):
        try:
            parsed_training = json.loads(training_raw or "{}")
        except json.JSONDecodeError:
            parsed_training = {}
        has_signal = bool(parsed_training) and any(
            bool(v) for v in parsed_training.values() if not isinstance(v, (dict, list))
        ) or any(
            isinstance(v, dict) and any(bool(x) for x in v.values())
            for v in (parsed_training or {}).values()
            if isinstance(v, dict)
        )
        if (
            has_signal or (tenant.context_pack_version or 0) > 0
        ) and not is_step_complete(state, "training"):
            state = mark_step_complete(state, "training")
            changed = True

    batch = session.exec(
        select(GenerationBatch)
        .where(GenerationBatch.tenant_id == tid)
        .limit(1)
    ).first()
    if batch and not is_step_complete(state, "generate"):
        state = mark_step_complete(state, "generate")
        changed = True

    reviewed = session.exec(
        select(ContentPost).where(
            ContentPost.tenant_id == tid,
            ContentPost.status == "approved",
        )
    ).first()
    published = session.exec(
        select(ContentPost).where(
            ContentPost.tenant_id == tid,
            ContentPost.status == "published",
        )
    ).first()
    if (reviewed or published) and not is_step_complete(state, "review"):
        state = mark_step_complete(state, "review")
        changed = True

    if published:
        if not is_step_complete(state, "publish"):
            state = mark_step_complete(state, "publish")
            changed = True
        if not state.get("completedAt") and not state.get("skipped"):
            state["completedAt"] = _iso(published.published_at or _utcnow())
            changed = True

    if changed:
        return save_tenant_onboarding(session, tenant, state)
    return public_onboarding(state)
