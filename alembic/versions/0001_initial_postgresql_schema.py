"""Initial PostgreSQL schema with ledger and staff authentication.

Revision ID: 0001_initial
Revises:
"""
import uuid

from alembic import op
from sqlalchemy import insert

from banking_api.models import Base, Branch, LedgerAccount


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


BALANCE_TRIGGER = """
CREATE OR REPLACE FUNCTION enforce_balanced_posted_transaction()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_id uuid;
    transaction_kind text;
    transaction_status text;
    posting_total bigint;
    posting_count bigint;
BEGIN
    IF TG_TABLE_NAME = 'ledger_entries' THEN
        IF TG_OP = 'DELETE' THEN
            target_id := OLD.transaction_id;
        ELSE
            target_id := NEW.transaction_id;
        END IF;
    ELSE
        IF TG_OP = 'DELETE' THEN
            target_id := OLD.id;
        ELSE
            target_id := NEW.id;
        END IF;
    END IF;

    SELECT kind, status
      INTO transaction_kind, transaction_status
      FROM ledger_transactions
     WHERE id = target_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF transaction_status = 'POSTED' THEN
        SELECT COALESCE(SUM(amount_minor), 0), COUNT(*)
          INTO posting_total, posting_count
          FROM ledger_entries
         WHERE transaction_id = target_id;
        IF posting_total <> 0 OR
           (transaction_kind <> 'ACCOUNT_STATUS' AND posting_count < 2) OR
           (transaction_kind = 'ACCOUNT_STATUS' AND posting_count <> 0) THEN
            RAISE EXCEPTION 'Posted transaction % has unbalanced ledger entries', target_id;
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
"""


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute(BALANCE_TRIGGER)
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ledger_entries_must_balance
        AFTER INSERT OR UPDATE OR DELETE ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_balanced_posted_transaction()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ledger_transactions_must_balance
        AFTER INSERT OR UPDATE ON ledger_transactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_balanced_posted_transaction()
        """
    )
    bind.execute(
        insert(Branch).values(
            ifsc="SHIV0000001",
            name="Main Branch",
            next_sequence=1,
        )
    )
    bind.execute(
        insert(LedgerAccount).values(
            id=uuid.uuid4(),
            code="SYSTEM:CASH_CLEARING",
            account_type="CASH_CLEARING",
            account_id=None,
        )
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS ledger_entries_must_balance ON ledger_entries")
    op.execute(
        "DROP TRIGGER IF EXISTS ledger_transactions_must_balance ON ledger_transactions"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_balanced_posted_transaction()")
    Base.metadata.drop_all(bind=op.get_bind())
