"""Allow legacy customers to receive generated CIF values.

Revision ID: 0005_legacy_cif_default
Revises: 0004_real_bank_features
"""
import sqlalchemy as sa

from alembic import op

revision = "0005_legacy_cif_default"
down_revision = "0004_real_bank_features"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("customers")
    }
    if "cif_number" in columns:
        op.execute(
            "ALTER TABLE customers ALTER COLUMN cif_number TYPE VARCHAR(64)"
        )
        op.execute(
            "ALTER TABLE customers ALTER COLUMN cif_number "
            "SET DEFAULT ('CIF-' || gen_random_uuid()::text)"
        )


def downgrade():
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("customers")
    }
    if "cif_number" in columns:
        op.execute(
            "ALTER TABLE customers ALTER COLUMN cif_number DROP DEFAULT"
        )
