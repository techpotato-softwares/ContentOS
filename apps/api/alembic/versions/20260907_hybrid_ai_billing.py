"""Hybrid AI billing foundation: tenant plan/mode/quota + ai_usage_events.

Safe for existing DBs: ADD COLUMN IF NOT EXISTS + backfill starter/platform defaults.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_hybrid_ai_billing"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    def _add_column(table: str, column: str, spec: str) -> None:
        if dialect == "postgresql":
            op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {spec}"))
            return
        # SQLite / others: inspect and add only when missing
        rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
        existing = {r[1] for r in rows}
        if column not in existing:
            op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {spec}"))

    _add_column("tenants", "plan", "VARCHAR DEFAULT 'starter'")
    _add_column("tenants", "ai_billing_mode", "VARCHAR DEFAULT 'platform'")
    _add_column("tenants", "ai_secret_arn", "VARCHAR")
    _add_column("tenants", "ai_posts_quota_monthly", "INTEGER DEFAULT 40")
    _add_column("tenants", "ai_posts_used_month", "INTEGER DEFAULT 0")
    _add_column("tenants", "ai_usage_month", "VARCHAR")
    _add_column("tenants", "stripe_customer_id", "VARCHAR")
    _add_column("tenants", "razorpay_customer_id", "VARCHAR")

    # Backfill existing rows without wiping custom values
    op.execute(sa.text("UPDATE tenants SET plan = 'starter' WHERE plan IS NULL OR plan = ''"))
    op.execute(
        sa.text(
            "UPDATE tenants SET ai_billing_mode = 'platform' "
            "WHERE ai_billing_mode IS NULL OR ai_billing_mode = ''"
        )
    )
    op.execute(
        sa.text("UPDATE tenants SET ai_posts_used_month = 0 WHERE ai_posts_used_month IS NULL")
    )
    op.execute(
        sa.text(
            "UPDATE tenants SET ai_posts_quota_monthly = 40 WHERE ai_posts_quota_monthly IS NULL"
        )
    )

    if dialect == "postgresql":
        op.execute(
            sa.text(
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
                """
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_usage_events_tenant_id "
                "ON ai_usage_events (tenant_id)"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_usage_events_kind "
                "ON ai_usage_events (kind)"
            )
        )
    else:
        # SQLite: create via SQLAlchemy table if missing
        exists = conn.execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_usage_events'"
            )
        ).fetchone()
        if not exists:
            op.create_table(
                "ai_usage_events",
                sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
                sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.tenant_id"), nullable=False),
                sa.Column("kind", sa.String(), nullable=False),
                sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("model", sa.String(), nullable=True),
                sa.Column("meta_json", sa.Text(), server_default="{}"),
                sa.Column("created_at", sa.DateTime(), nullable=True),
            )
            op.create_index("ix_ai_usage_events_tenant_id", "ai_usage_events", ["tenant_id"])
            op.create_index("ix_ai_usage_events_kind", "ai_usage_events", ["kind"])


def downgrade() -> None:
    op.drop_table("ai_usage_events")
    # Columns left in place on downgrade to avoid data loss on shared DBs.
