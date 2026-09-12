"""Create email_otp_challenges for Wave 1 passwordless login."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260326_01_email_otp"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_otp_challenges",
        sa.Column("otp_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False, server_default="login"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("request_ip", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_otp_challenges_email", "email_otp_challenges", ["email"])
    op.create_index(
        "ix_email_otp_challenges_purpose", "email_otp_challenges", ["purpose"]
    )
    op.create_index(
        "ix_email_otp_challenges_expires_at", "email_otp_challenges", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_email_otp_challenges_expires_at", table_name="email_otp_challenges")
    op.drop_index("ix_email_otp_challenges_purpose", table_name="email_otp_challenges")
    op.drop_index("ix_email_otp_challenges_email", table_name="email_otp_challenges")
    op.drop_table("email_otp_challenges")
