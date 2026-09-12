"""Add tenants.onboarding_json for first-run wizard progress.

Revision ID: 20260912_01_tenant_onboarding
Revises: 20260910_01_tenant_invites
Create Date: 2026-09-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260912_01_tenant_onboarding"
down_revision = "20260910_01_tenant_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("tenants")}
    if "onboarding_json" not in cols:
        op.add_column(
            "tenants",
            sa.Column(
                "onboarding_json",
                sa.Text(),
                nullable=False,
                server_default="{}",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("tenants")}
    if "onboarding_json" in cols:
        op.drop_column("tenants", "onboarding_json")
