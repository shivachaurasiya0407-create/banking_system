"""Add linked reversal transactions.

Revision ID: 0002_reversals
Revises: 0001_initial
"""
from alembic import op

revision = "0002_reversals"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE ledger_transactions ADD COLUMN IF NOT EXISTS "
        "reversal_of_id UUID REFERENCES ledger_transactions(id) ON DELETE RESTRICT"
    )
    op.execute(
        "ALTER TABLE ledger_transactions DROP CONSTRAINT IF EXISTS ck_ledger_transaction_kind"
    )
    op.execute(
        "ALTER TABLE ledger_transactions ADD CONSTRAINT ck_ledger_transaction_kind "
        "CHECK (kind IN ('OPENING_DEPOSIT', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', "
        "'ACCOUNT_STATUS', 'REVERSAL'))"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_transactions_reversal_of "
        "ON ledger_transactions (reversal_of_id) WHERE reversal_of_id IS NOT NULL"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_ledger_transactions_reversal_of")
    op.execute("ALTER TABLE ledger_transactions DROP COLUMN IF EXISTS reversal_of_id")
    op.execute(
        "ALTER TABLE ledger_transactions DROP CONSTRAINT IF EXISTS ck_ledger_transaction_kind"
    )
    op.execute(
        "ALTER TABLE ledger_transactions ADD CONSTRAINT ck_ledger_transaction_kind "
        "CHECK (kind IN ('OPENING_DEPOSIT', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'ACCOUNT_STATUS'))"
    )