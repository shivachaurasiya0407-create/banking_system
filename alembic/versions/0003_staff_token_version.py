"""Add staff token-version counter for session revocation.

Revision ID: 0003_staff_tokens
Revises: 0002_reversals
"""
from alembic import op

revision = "0003_staff_tokens"
down_revision = "0002_reversals"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS "
        "token_version INTEGER NOT NULL DEFAULT 0"
    )


def downgrade():
    op.execute("ALTER TABLE staff_users DROP COLUMN IF EXISTS token_version")