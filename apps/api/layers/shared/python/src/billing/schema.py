"""Runtime ALTER helpers so existing Supabase/local DBs pick up billing columns without downtime."""
from __future__ import annotations

from utils.logger import logger


def ensure_tenant_billing_schema() -> None:
    """Idempotent ADD COLUMN / CREATE TABLE for hybrid AI billing foundation."""
    try:
        from sqlalchemy import text
        from database import get_engine

        stmts = [
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan VARCHAR DEFAULT 'starter'",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS ai_billing_mode VARCHAR DEFAULT 'platform'",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS ai_secret_arn VARCHAR",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS ai_posts_quota_monthly INTEGER DEFAULT 40",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS ai_posts_used_month INTEGER DEFAULT 0",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS ai_usage_month VARCHAR",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR",
            "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS razorpay_customer_id VARCHAR",
            """
            CREATE TABLE IF NOT EXISTS ai_usage_events (
                event_id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(tenant_id),
                kind VARCHAR NOT NULL,
                units INTEGER NOT NULL DEFAULT 1,
                model VARCHAR,
                meta_json TEXT DEFAULT '{}',
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_ai_usage_events_tenant_id ON ai_usage_events (tenant_id)",
            "UPDATE tenants SET plan = 'starter' WHERE plan IS NULL OR plan = ''",
            "UPDATE tenants SET ai_billing_mode = 'platform' WHERE ai_billing_mode IS NULL OR ai_billing_mode = ''",
            "UPDATE tenants SET ai_posts_used_month = 0 WHERE ai_posts_used_month IS NULL",
            """
            UPDATE tenants SET ai_posts_quota_monthly = 40
            WHERE ai_posts_quota_monthly IS NULL
            """,
        ]
        with get_engine().begin() as conn:
            for sql in stmts:
                try:
                    conn.execute(text(sql))
                except Exception as exc:
                    logger.warn("billing schema statement skipped", {"error": str(exc)})
    except Exception as exc:
        logger.warn("ensure_tenant_billing_schema failed", {"error": str(exc)})
