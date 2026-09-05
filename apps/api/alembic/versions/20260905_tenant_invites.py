"""Add tenant_invites table for team invitations.

Revision ID: 20260905_tenant_invites
Revises:
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa

revision = "20260905_tenant_invites"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_invites",
        sa.Column("invite_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="tenant_member"),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tenant_invites_tenant_id", "tenant_invites", ["tenant_id"])
    op.create_index("ix_tenant_invites_email", "tenant_invites", ["email"])
    op.create_index("ix_tenant_invites_token", "tenant_invites", ["token"], unique=True)
    op.create_index("ix_tenant_invites_status", "tenant_invites", ["status"])
    op.create_index("ix_tenant_invites_expires_at", "tenant_invites", ["expires_at"])
    op.create_index("ix_tenant_invites_role", "tenant_invites", ["role"])


def downgrade() -> None:
    op.drop_table("tenant_invites")
