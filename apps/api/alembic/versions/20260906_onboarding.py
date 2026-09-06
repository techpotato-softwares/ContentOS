"""Add tenants.onboarding_json for first-run wizard.

Revision ID: 20260906_onboarding
Revises: 20260905_tenant_invites
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260906_onboarding"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("onboarding_json", sa.Text(), nullable=True, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "onboarding_json")
