"""Hybrid AI billing foundation — catalog, defaults, migration, usage events, redaction."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers/shared/python/src"))
sys.path.insert(0, str(ROOT))

from billing import (  # noqa: E402
    PLAN_CATALOG,
    apply_billing_defaults,
    get_plan,
    redact_secrets,
    tenant_billing_public,
)
from database.models import AiUsageEvent, Tenant  # noqa: E402
import database.models  # noqa: F401,E402


def test_plan_catalog_limits_and_display_hooks():
    assert set(PLAN_CATALOG) == {"starter", "growth", "scale", "agency"}
    starter = get_plan("starter")
    assert starter.ai_posts_quota_monthly == 40
    assert starter.byok_allowed is False
    assert starter.monthly_usd == 49
    assert starter.monthly_inr > 0
    pub = starter.public_dict()
    assert pub["display"]["usd"].startswith("$")
    assert "₹" in pub["display"]["inr"]
    assert get_plan("growth").byok_allowed is True
    assert get_plan("agency").byok_required is True
    assert get_plan("agency").ai_posts_quota_monthly == 0
    assert get_plan("unknown").id == "starter"


def test_apply_billing_defaults_starter_platform():
    t = Tenant(name="Acme", slug="acme-billing-test")
    apply_billing_defaults(t)
    assert t.plan == "starter"
    assert t.ai_billing_mode == "platform"
    assert t.ai_posts_quota_monthly == 40
    assert t.ai_posts_used_month == 0


def test_secret_redaction_strips_provider_keys():
    raw = {
        "plan": "starter",
        "openaiApiKey": "sk-secret-should-vanish",
        "OPENAI_API_KEY": "sk-also-gone",
        "ai_secret_arn": "arn:aws:secretsmanager:…",
        "gemini_api_key": "AIzaSyFake",
        "nested": {"api_key": "sk-nested", "ok": True},
        "stripe_customer_id": "cus_123",  # not an API secret — may remain if not filtered by name
    }
    clean = redact_secrets(raw)
    blob = json.dumps(clean)
    assert "sk-" not in blob
    assert "AIza" not in blob
    assert "ai_secret_arn" not in clean
    assert "openaiApiKey" not in clean
    assert "OPENAI_API_KEY" not in clean
    assert clean["plan"] == "starter"
    assert clean["nested"]["ok"] is True
    assert "api_key" not in clean["nested"]


def test_tenant_billing_public_never_exposes_secrets():
    t = Tenant(
        name="Sec",
        slug="sec-billing",
        plan="growth",
        ai_billing_mode="byok",
        ai_secret_arn="arn:aws:secretsmanager:secret:tenant-ai",
        ai_posts_quota_monthly=150,
        ai_posts_used_month=3,
        ai_usage_month="2026-09",
    )
    pub = tenant_billing_public(t)
    blob = json.dumps(pub)
    assert "arn:aws" not in blob
    assert "sk-" not in blob
    assert pub["plan"] == "growth"
    assert pub["aiBillingMode"] == "byok"
    assert pub["byokConfigured"] is True
    assert pub["byokAllowed"] is True
    assert pub["quota"]["remaining"] == 147
    assert isinstance(pub["plans"], list) and len(pub["plans"]) == 4


def test_ai_usage_event_tenant_scoped(tmp_path):
    db_path = tmp_path / "billing.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        a = Tenant(name="A", slug="tenant-a")
        b = Tenant(name="B", slug="tenant-b")
        apply_billing_defaults(a)
        apply_billing_defaults(b)
        session.add(a)
        session.add(b)
        session.commit()
        session.refresh(a)
        session.refresh(b)
        session.add(
            AiUsageEvent(
                tenant_id=a.tenant_id,
                kind="generate_batch",
                units=3,
                model="gpt-4o-mini",
                meta_json=json.dumps({"billingMode": "platform"}),
            )
        )
        session.add(
            AiUsageEvent(
                tenant_id=b.tenant_id,
                kind="chat",
                units=1,
                model="gemini-2.0-flash",
                meta_json="{}",
            )
        )
        session.commit()
        a_events = session.exec(
            select(AiUsageEvent).where(AiUsageEvent.tenant_id == a.tenant_id)
        ).all()
        b_events = session.exec(
            select(AiUsageEvent).where(AiUsageEvent.tenant_id == b.tenant_id)
        ).all()
        assert len(a_events) == 1
        assert a_events[0].kind == "generate_batch"
        assert a_events[0].units == 3
        assert len(b_events) == 1
        assert b_events[0].tenant_id == b.tenant_id


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    os.environ["DATABASE_URL"] = db_url
    return cfg


def test_alembic_upgrade_head_fresh_db(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'fresh.db'}"
    engine = create_engine(db_url)
    # Pre-create base tenants table (as an existing app schema without billing)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tenants (
                    tenant_id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL UNIQUE,
                    modules_enabled VARCHAR,
                    is_active BOOLEAN DEFAULT 1,
                    training_json TEXT,
                    context_pack_cached TEXT,
                    context_pack_version INTEGER DEFAULT 0,
                    ui_mode VARCHAR,
                    app_display_name VARCHAR,
                    logo_url VARCHAR,
                    primary_color VARCHAR,
                    secondary_color VARCHAR,
                    accent_color VARCHAR,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO tenants (tenant_id, name, slug, training_json, ui_mode) "
                "VALUES (1, 'Legacy', 'legacy-co', '{}', 'platform')"
            )
        )

    command.upgrade(_alembic_cfg(db_url), "head")

    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("tenants")}
    for required in (
        "plan",
        "ai_billing_mode",
        "ai_posts_quota_monthly",
        "ai_posts_used_month",
        "ai_usage_month",
        "stripe_customer_id",
        "razorpay_customer_id",
        "ai_secret_arn",
    ):
        assert required in cols
    assert "ai_usage_events" in insp.get_table_names()

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT plan, ai_billing_mode, ai_posts_quota_monthly FROM tenants WHERE tenant_id=1")
        ).one()
        assert row[0] == "starter"
        assert row[1] == "platform"
        assert row[2] == 40


def test_alembic_upgrade_head_idempotent_on_existing(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'existing.db'}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tenants (
                    tenant_id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    slug VARCHAR NOT NULL UNIQUE,
                    modules_enabled VARCHAR,
                    is_active BOOLEAN DEFAULT 1,
                    training_json TEXT,
                    context_pack_cached TEXT,
                    context_pack_version INTEGER DEFAULT 0,
                    ui_mode VARCHAR,
                    app_display_name VARCHAR,
                    logo_url VARCHAR,
                    primary_color VARCHAR,
                    secondary_color VARCHAR,
                    accent_color VARCHAR,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO tenants (tenant_id, name, slug, training_json) "
                "VALUES (1, 'X', 'x-co', '{}')"
            )
        )

    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # second run should be a no-op at alembic level

    with engine.connect() as conn:
        # Simulate ensure-style re-add safety by checking columns still present
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(tenants)")).fetchall()]
        assert "plan" in cols
        assert "stripe_customer_id" in cols
