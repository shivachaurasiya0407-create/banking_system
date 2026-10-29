"""Bind each staff login to one active device session.

Revision ID: 0006_staff_device_sessions
Revises: 0005_legacy_cif_default
"""
import sqlalchemy as sa

from alembic import op

revision = "0006_staff_device_sessions"
down_revision = "0005_legacy_cif_default"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS active_session_id VARCHAR(36)"
    )
    op.execute(
        "ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE"
    )


def downgrade():
    op.execute("ALTER TABLE staff_users DROP COLUMN IF EXISTS last_login_at")
    op.execute("ALTER TABLE staff_users DROP COLUMN IF EXISTS active_session_id")
