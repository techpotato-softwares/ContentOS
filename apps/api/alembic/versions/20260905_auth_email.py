"""Add email_verified_at, token_version, and auth_tokens table.

Revision ID: 20260905_auth_email
Revises:
Create Date: 2026-09-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260905_auth_email"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("users")} if insp.has_table("users") else set()
    if "email_verified_at" not in cols:
        op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    if "token_version" not in cols:
        op.add_column(
            "users",
            sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        )
    if not insp.has_table("auth_tokens"):
        op.create_table(
            "auth_tokens",
            sa.Column("token_id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
            sa.Column("purpose", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("request_key", sa.String(), nullable=True),
        )
        op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
        op.create_index("ix_auth_tokens_purpose", "auth_tokens", ["purpose"])
        op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)
        op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"])
        op.create_index("ix_auth_tokens_request_key", "auth_tokens", ["request_key"])


def downgrade() -> None:
    op.drop_table("auth_tokens")
    op.drop_column("users", "token_version")
    op.drop_column("users", "email_verified_at")
