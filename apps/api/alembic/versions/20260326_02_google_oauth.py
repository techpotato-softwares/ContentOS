"""Create Google OAuth columns + oauth_login_states (Wave 1)."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260326_02_google_oauth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(), nullable=False, server_default="password"),
    )
    op.add_column("users", sa.Column("google_sub", sa.String(), nullable=True))
    # password becomes nullable for Google-only accounts
    op.alter_column("users", "password", existing_type=sa.String(), nullable=True)
    op.create_index("ix_users_auth_provider", "users", ["auth_provider"])
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    op.create_table(
        "oauth_login_states",
        sa.Column("state_id", sa.String(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False, server_default="google"),
        sa.Column("kind", sa.String(), nullable=False, server_default="csrf"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_oauth_login_states_provider", "oauth_login_states", ["provider"])
    op.create_index("ix_oauth_login_states_kind", "oauth_login_states", ["kind"])
    op.create_index("ix_oauth_login_states_expires_at", "oauth_login_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_oauth_login_states_expires_at", table_name="oauth_login_states")
    op.drop_index("ix_oauth_login_states_kind", table_name="oauth_login_states")
    op.drop_index("ix_oauth_login_states_provider", table_name="oauth_login_states")
    op.drop_table("oauth_login_states")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_index("ix_users_auth_provider", table_name="users")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "auth_provider")
    op.alter_column("users", "password", existing_type=sa.String(), nullable=False)
