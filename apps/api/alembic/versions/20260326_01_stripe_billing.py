"""Add Stripe + hybrid AI billing columns on tenants.

Revision ID: 20260326_01_stripe_billing
Revises:
Create Date: 2026-03-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260326_01_stripe_billing"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("ai_billing_mode", sa.String(), nullable=False, server_default="platform"),
    )
    op.add_column(
        "tenants",
        sa.Column("plan_tier", sa.String(), nullable=False, server_default="starter"),
    )
    op.add_column("tenants", sa.Column("ai_secret_arn", sa.String(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("ai_posts_quota_monthly", sa.Integer(), nullable=False, server_default="40"),
    )
    op.add_column(
        "tenants",
        sa.Column("ai_posts_used_month", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("tenants", sa.Column("ai_usage_month", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("stripe_subscription_id", sa.String(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("billing_status", sa.String(), nullable=False, server_default="none"),
    )
    op.create_index("ix_tenants_stripe_customer_id", "tenants", ["stripe_customer_id"])
    op.create_index("ix_tenants_stripe_subscription_id", "tenants", ["stripe_subscription_id"])

    op.create_table(
        "ai_usage_events",
        sa.Column("event_id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("billing_mode", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_stripe_webhook_events_event_id", "stripe_webhook_events", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_stripe_webhook_events_event_id", table_name="stripe_webhook_events")
    op.drop_table("stripe_webhook_events")
    op.drop_table("ai_usage_events")
    op.drop_index("ix_tenants_stripe_subscription_id", table_name="tenants")
    op.drop_index("ix_tenants_stripe_customer_id", table_name="tenants")
    for col in (
        "billing_status",
        "stripe_subscription_id",
        "stripe_customer_id",
        "ai_usage_month",
        "ai_posts_used_month",
        "ai_posts_quota_monthly",
        "ai_secret_arn",
        "plan_tier",
        "ai_billing_mode",
    ):
        op.drop_column("tenants", col)
