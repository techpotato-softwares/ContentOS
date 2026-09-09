"""Add linkedin_sub for LinkedIn OIDC login (separate from publishing SocialAccount)."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260326_03_linkedin_oidc"
down_revision = "20260326_02_google_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("linkedin_sub", sa.String(), nullable=True))
    op.create_index("ix_users_linkedin_sub", "users", ["linkedin_sub"], unique=True)
    op.add_column("oauth_login_states", sa.Column("nonce", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("oauth_login_states", "nonce")
    op.drop_index("ix_users_linkedin_sub", table_name="users")
    op.drop_column("users", "linkedin_sub")
