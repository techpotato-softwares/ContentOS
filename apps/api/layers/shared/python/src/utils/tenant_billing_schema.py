"""Ensure tenant billing columns exist (SQLite/local + older DBs without Alembic)."""
from __future__ import annotations

from sqlalchemy import text

from database import get_engine
from utils.logger import logger

_ensured = False

_COLUMNS: list[tuple[str, str]] = [
    ("ai_billing_mode", "VARCHAR DEFAULT 'platform'"),
    ("plan_tier", "VARCHAR DEFAULT 'starter'"),
    ("ai_secret_arn", "VARCHAR"),
    ("ai_posts_quota_monthly", "INTEGER DEFAULT 40"),
    ("ai_posts_used_month", "INTEGER DEFAULT 0"),
    ("ai_usage_month", "VARCHAR"),
    ("billing_gateway", "VARCHAR"),
    ("stripe_customer_id", "VARCHAR"),
    ("stripe_subscription_id", "VARCHAR"),
    ("razorpay_customer_id", "VARCHAR"),
    ("razorpay_subscription_id", "VARCHAR"),
    ("billing_status", "VARCHAR DEFAULT 'none'"),
]


def ensure_tenant_billing_columns() -> None:
    global _ensured
    if _ensured:
        return
    try:
        engine = get_engine()
        with engine.begin() as conn:
            dialect = engine.dialect.name
            for col, ddl in _COLUMNS:
                if dialect == "sqlite":
                    rows = conn.execute(text("PRAGMA table_info(tenants)")).fetchall()
                    existing = {r[1] for r in rows}
                    if col not in existing:
                        conn.execute(text(f"ALTER TABLE tenants ADD COLUMN {col} {ddl}"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col} {ddl}")
                    )
            if dialect == "sqlite":
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
                            id INTEGER PRIMARY KEY,
                            event_id VARCHAR UNIQUE,
                            event_type VARCHAR,
                            processed_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS razorpay_webhook_events (
                            id INTEGER PRIMARY KEY,
                            event_id VARCHAR UNIQUE,
                            event_type VARCHAR,
                            processed_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS ai_usage_events (
                            event_id INTEGER PRIMARY KEY,
                            tenant_id INTEGER,
                            user_id INTEGER,
                            action VARCHAR,
                            units INTEGER,
                            billing_mode VARCHAR,
                            provider VARCHAR,
                            created_at DATETIME
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS razorpay_webhook_events (
                            id SERIAL PRIMARY KEY,
                            event_id VARCHAR UNIQUE,
                            event_type VARCHAR NOT NULL,
                            processed_at TIMESTAMP NOT NULL
                        )
                        """
                    )
                )
        _ensured = True
    except Exception as exc:
        logger.warn("ensure_tenant_billing_columns failed", {"error": str(exc)})
