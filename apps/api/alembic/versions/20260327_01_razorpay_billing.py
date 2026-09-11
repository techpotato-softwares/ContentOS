"""Add Razorpay billing columns + webhook ledger.

Revision ID: 20260327_01_razorpay_billing
Revises: 20260326_01_stripe_billing
Create Date: 2026-03-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260327_01_razorpay_billing"
down_revision = "20260326_01_stripe_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("billing_gateway", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("razorpay_customer_id", sa.String(), nullable=True))
    op.add_column(
        "tenants", sa.Column("razorpay_subscription_id", sa.String(), nullable=True)
    )
    op.create_index("ix_tenants_razorpay_customer_id", "tenants", ["razorpay_customer_id"])
    op.create_index(
        "ix_tenants_razorpay_subscription_id", "tenants", ["razorpay_subscription_id"]
    )

    op.create_table(
        "razorpay_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_razorpay_webhook_events_event_id", "razorpay_webhook_events", ["event_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_razorpay_webhook_events_event_id", table_name="razorpay_webhook_events"
    )
    op.drop_table("razorpay_webhook_events")
    op.drop_index("ix_tenants_razorpay_subscription_id", table_name="tenants")
    op.drop_index("ix_tenants_razorpay_customer_id", table_name="tenants")
    for col in ("razorpay_subscription_id", "razorpay_customer_id", "billing_gateway"):
        op.drop_column("tenants", col)
