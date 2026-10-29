"""Separate owner-issued API tokens; preserve all existing data and sessions."""

import sqlalchemy as sa

from alembic import op

revision = "0003_api_tokens"
down_revision = "0002_authentication"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_api_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_auth_api_tokens_expires_at", "auth_api_tokens", ["expires_at"])
    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='demand_demo_reader') THEN
        REVOKE ALL ON auth_api_tokens FROM demand_demo_reader;
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='demand_app') THEN
        REVOKE ALL ON auth_api_tokens FROM demand_app;
        GRANT SELECT ON auth_api_tokens TO demand_app;
      END IF;
    END $$;
    """)


def downgrade():
    op.drop_table("auth_api_tokens")
