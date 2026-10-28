"""Add users and revocable sessions without modifying application data."""

import sqlalchemy as sa

from alembic import op

revision = "0002_authentication"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('admin', 'viewer')", name="valid_role"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_user_expiry", "auth_sessions", ["user_id", "expires_at"])
    # Role names are fixed by this repo's isolated PostgreSQL initialization.
    # Existing non-Docker/dev databases may not have these roles.
    op.execute("""
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='demand_demo_reader') THEN
        REVOKE ALL ON auth_users, auth_sessions FROM demand_demo_reader;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM demand_demo_reader;
        GRANT SELECT ON stores, products, sales_history, inventory, forecast_runs,
          forecast_run_logs, product_forecasts, stock_recommendations TO demand_demo_reader;
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='demand_app') THEN
        REVOKE ALL ON auth_users FROM demand_app;
        GRANT SELECT ON auth_users TO demand_app;
        GRANT UPDATE(password_hash) ON auth_users TO demand_app;
      END IF;
    END $$;
    """)


def downgrade():
    op.drop_table("auth_sessions")
    op.drop_table("auth_users")
