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
    op.add_column(
        "staff_users",
        sa.Column("active_session_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "staff_users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("staff_users", "last_login_at")
    op.drop_column("staff_users", "active_session_id")
