"""Real-bank upgrade: account_type, KYC, loans, FDs, interest, notifications.

Revision ID: 0004_real_bank_features
Revises: 0003_staff_token_version
"""
import sqlalchemy as sa

from alembic import op

revision = "0004_real_bank_features"
down_revision = "0003_staff_tokens"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 1. customers: add KYC + profile columns ──────────────────────────────
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS email VARCHAR(200)")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(250)")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS address_city VARCHAR(100)")
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS address_pin VARCHAR(10)")
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS kyc_status VARCHAR(20) "
        "NOT NULL DEFAULT 'PENDING'"
    )
    # Drop old check if any, add KYC check
    op.execute(
        "ALTER TABLE customers DROP CONSTRAINT IF EXISTS ck_customer_kyc_status"
    )
    op.execute(
        "ALTER TABLE customers ADD CONSTRAINT ck_customer_kyc_status "
        "CHECK (kyc_status IN ('PENDING', 'VERIFIED', 'REJECTED'))"
    )
    customer_columns = {column["name"] for column in inspector.get_columns("customers")}
    if "cif_number" in customer_columns:
        op.execute(
            "ALTER TABLE customers ALTER COLUMN cif_number TYPE VARCHAR(64)"
        )
        op.execute(
            "ALTER TABLE customers ALTER COLUMN cif_number "
            "SET DEFAULT ('CIF-' || gen_random_uuid()::text)"
        )
    if "address" in customer_columns:
        op.execute(
            "UPDATE customers SET address_line1 = address "
            "WHERE address_line1 IS NULL AND address IS NOT NULL"
        )

    # ── 2. accounts: add account_type, interest_rate, daily_limit ───────────
    op.execute(
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) "
        "NOT NULL DEFAULT 'SAVINGS'"
    )
    op.execute(
        "ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_account_type"
    )
    op.execute(
        "ALTER TABLE accounts ADD CONSTRAINT ck_account_type "
        "CHECK (account_type IN ('SAVINGS', 'CURRENT', 'SALARY'))"
    )
    op.execute(
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS interest_rate_annual NUMERIC(6,4)"
    )
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "interest_rate" in account_columns:
        op.execute(
            "UPDATE accounts SET interest_rate_annual = interest_rate::numeric "
            "WHERE interest_rate IS NOT NULL"
        )
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN interest_rate_annual SET DEFAULT 3.5000"
    )
    op.execute(
        "UPDATE accounts SET interest_rate_annual = 3.5000 "
        "WHERE interest_rate_annual IS NULL"
    )
    op.execute(
        "ALTER TABLE accounts ALTER COLUMN interest_rate_annual SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS daily_withdrawal_limit_minor "
        "BIGINT NOT NULL DEFAULT 0"
    )

    # ── 3. ledger_transactions: extend kind check to include new types ────────
    op.execute(
        "ALTER TABLE ledger_transactions DROP CONSTRAINT IF EXISTS ck_ledger_transaction_kind"
    )
    op.execute(
        "ALTER TABLE ledger_transactions ADD CONSTRAINT ck_ledger_transaction_kind "
        "CHECK (kind IN ('OPENING_DEPOSIT', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', "
        "'ACCOUNT_STATUS', 'REVERSAL', 'INTEREST', 'LOAN_DISBURSEMENT', "
        "'LOAN_REPAYMENT', 'FD_OPEN', 'FD_MATURITY', 'FD_PREMATURE_CLOSURE'))"
    )

    # ── 4. ledger_accounts: extend type check ───────────────────────────────
    op.execute(
        "ALTER TABLE ledger_accounts DROP CONSTRAINT IF EXISTS ck_ledger_account_type"
    )
    op.execute(
        "ALTER TABLE ledger_accounts ADD CONSTRAINT ck_ledger_account_type "
        "CHECK (account_type IN ('CUSTOMER_DEPOSIT', 'CASH_CLEARING', "
        "'INTEREST_EXPENSE', 'LOAN_RECEIVABLE', 'FD_LIABILITY'))"
    )

    # ── 5. loans table ───────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS loans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID,
            account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
            loan_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'APPLIED',
            principal_minor BIGINT NOT NULL,
            outstanding_minor BIGINT NOT NULL,
            interest_rate_annual NUMERIC(6,4),
            tenure_months INTEGER NOT NULL,
            emi_minor BIGINT NOT NULL DEFAULT 0,
            disbursed_at TIMESTAMPTZ,
            next_emi_date DATE,
            closed_at TIMESTAMPTZ,
            approved_by_id UUID REFERENCES staff_users(id) ON DELETE SET NULL,
            memo VARCHAR(500) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE loans ADD COLUMN IF NOT EXISTS customer_id UUID")
    op.execute(
        "ALTER TABLE loans ADD COLUMN IF NOT EXISTS interest_rate_annual NUMERIC(6,4)"
    )
    op.execute("ALTER TABLE loans ADD COLUMN IF NOT EXISTS emi_minor BIGINT NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE loans ADD COLUMN IF NOT EXISTS disbursed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE loans ADD COLUMN IF NOT EXISTS next_emi_date DATE")
    op.execute("ALTER TABLE loans ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE loans ADD COLUMN IF NOT EXISTS approved_by_id UUID")
    op.execute(
        "ALTER TABLE loans ADD COLUMN IF NOT EXISTS memo VARCHAR(500) NOT NULL DEFAULT ''"
    )
    loan_columns = {column["name"] for column in inspector.get_columns("loans")}
    if "interest_rate" in loan_columns:
        op.execute(
            "UPDATE loans SET interest_rate_annual = interest_rate::numeric "
            "WHERE interest_rate_annual IS NULL"
        )
    if "monthly_emi_minor" in loan_columns:
        op.execute(
            "UPDATE loans SET emi_minor = monthly_emi_minor "
            "WHERE emi_minor = 0 AND monthly_emi_minor IS NOT NULL"
        )
    if "purpose" in loan_columns:
        op.execute(
            "UPDATE loans SET memo = purpose WHERE memo = '' AND purpose IS NOT NULL"
        )
    op.execute(
        "UPDATE loans AS loan SET customer_id = account.customer_id "
        "FROM accounts AS account "
        "WHERE loan.account_id = account.id AND loan.customer_id IS NULL"
    )
    op.execute(
        "UPDATE loans SET status = CASE status "
        "WHEN 'PENDING' THEN 'APPLIED' WHEN 'DISBURSED' THEN 'ACTIVE' "
        "ELSE status END"
    )
    if "disbursed_at" not in loan_columns and "created_at" in loan_columns:
        op.execute(
            "UPDATE loans SET disbursed_at = created_at "
            "WHERE status = 'ACTIVE' AND disbursed_at IS NULL"
        )
    op.execute("UPDATE loans SET interest_rate_annual = 0 WHERE interest_rate_annual IS NULL")
    op.execute("ALTER TABLE loans ALTER COLUMN customer_id SET NOT NULL")
    op.execute("ALTER TABLE loans ALTER COLUMN interest_rate_annual SET NOT NULL")
    op.execute("ALTER TABLE loans ALTER COLUMN interest_rate_annual SET DEFAULT 0")
    for legacy_column in ("loan_number", "interest_rate", "monthly_emi_minor", "paid_emis", "purpose"):
        if legacy_column in loan_columns:
            op.execute(f"ALTER TABLE loans ALTER COLUMN {legacy_column} DROP NOT NULL")
    op.execute("ALTER TABLE loans DROP CONSTRAINT IF EXISTS ck_loan_status")
    op.execute(
        "ALTER TABLE loans ADD CONSTRAINT ck_loan_status "
        "CHECK (status IN ('APPLIED', 'APPROVED', 'ACTIVE', 'CLOSED', 'REJECTED', 'DEFAULTED'))"
    )
    op.execute("ALTER TABLE loans DROP CONSTRAINT IF EXISTS ck_loan_type")
    op.execute(
        "ALTER TABLE loans ADD CONSTRAINT ck_loan_type "
        "CHECK (loan_type IN ('PERSONAL', 'HOME', 'VEHICLE', 'EDUCATION', 'GOLD'))"
    )
    op.execute("ALTER TABLE loans DROP CONSTRAINT IF EXISTS ck_loan_positive_principal")
    op.execute(
        "ALTER TABLE loans ADD CONSTRAINT ck_loan_positive_principal CHECK (principal_minor > 0)"
    )
    op.execute("ALTER TABLE loans DROP CONSTRAINT IF EXISTS ck_loan_positive_tenure")
    op.execute(
        "ALTER TABLE loans ADD CONSTRAINT ck_loan_positive_tenure CHECK (tenure_months > 0)"
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'loans_customer_id_fkey'
            ) THEN
                ALTER TABLE loans ADD CONSTRAINT loans_customer_id_fkey
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_loans_customer_id ON loans(customer_id)")

    # ── 6. loan_repayments table ─────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS loan_repayments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE RESTRICT,
            transaction_id UUID NOT NULL REFERENCES ledger_transactions(id) ON DELETE RESTRICT,
            amount_minor BIGINT NOT NULL,
            principal_component_minor BIGINT NOT NULL,
            interest_component_minor BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_loan_repayments_loan_id ON loan_repayments(loan_id)"
    )

    # ── 7. fixed_deposits table ──────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fixed_deposits (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID,
            account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
            status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            principal_minor BIGINT NOT NULL,
            interest_rate_annual NUMERIC(6,4),
            tenure_days INTEGER,
            maturity_date DATE NOT NULL,
            maturity_amount_minor BIGINT NOT NULL,
            premature_penalty_rate NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
            opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            closed_at TIMESTAMPTZ,
            transaction_id UUID
        )
        """
    )
    op.execute(
        "ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS customer_id UUID"
    )
    op.execute(
        "ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS interest_rate_annual NUMERIC(6,4)"
    )
    op.execute("ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS tenure_days INTEGER")
    op.execute(
        "ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS premature_penalty_rate "
        "NUMERIC(5,4) NOT NULL DEFAULT 1.0000"
    )
    op.execute("ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ")
    op.execute("ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE fixed_deposits ADD COLUMN IF NOT EXISTS transaction_id UUID")
    fd_columns = {column["name"] for column in inspector.get_columns("fixed_deposits")}
    if "interest_rate" in fd_columns:
        op.execute(
            "UPDATE fixed_deposits SET interest_rate_annual = interest_rate::numeric "
            "WHERE interest_rate_annual IS NULL"
        )
    if "tenure_months" in fd_columns:
        op.execute(
            "UPDATE fixed_deposits SET tenure_days = GREATEST(7, tenure_months * 30) "
            "WHERE tenure_days IS NULL"
        )
    if "start_date" in fd_columns:
        op.execute(
            "UPDATE fixed_deposits SET opened_at = start_date "
            "WHERE opened_at IS NULL"
        )
    if "created_at" in fd_columns:
        op.execute(
            "UPDATE fixed_deposits SET opened_at = created_at WHERE opened_at IS NULL"
        )
    op.execute(
        "UPDATE fixed_deposits AS fd SET customer_id = account.customer_id "
        "FROM accounts AS account "
        "WHERE fd.account_id = account.id AND fd.customer_id IS NULL"
    )
    op.execute(
        "UPDATE fixed_deposits SET status = CASE status "
        "WHEN 'PREMATURE_CLOSED' THEN 'CLOSED' ELSE status END"
    )
    op.execute(
        "UPDATE fixed_deposits SET interest_rate_annual = 0 "
        "WHERE interest_rate_annual IS NULL"
    )
    op.execute("UPDATE fixed_deposits SET tenure_days = 7 WHERE tenure_days IS NULL")
    op.execute("UPDATE fixed_deposits SET opened_at = now() WHERE opened_at IS NULL")
    op.execute("ALTER TABLE fixed_deposits ALTER COLUMN customer_id SET NOT NULL")
    op.execute(
        "ALTER TABLE fixed_deposits ALTER COLUMN interest_rate_annual SET NOT NULL"
    )
    op.execute("ALTER TABLE fixed_deposits ALTER COLUMN tenure_days SET NOT NULL")
    op.execute("ALTER TABLE fixed_deposits ALTER COLUMN opened_at SET NOT NULL")
    op.execute(
        "ALTER TABLE fixed_deposits ALTER COLUMN interest_rate_annual SET DEFAULT 0"
    )
    for legacy_column in ("fd_number", "interest_rate", "tenure_months", "start_date"):
        if legacy_column in fd_columns:
            op.execute(
                f"ALTER TABLE fixed_deposits ALTER COLUMN {legacy_column} DROP NOT NULL"
            )
    op.execute(
        "ALTER TABLE fixed_deposits ALTER COLUMN maturity_date TYPE DATE "
        "USING maturity_date::date"
    )
    op.execute("ALTER TABLE fixed_deposits DROP CONSTRAINT IF EXISTS ck_fd_status")
    op.execute(
        "ALTER TABLE fixed_deposits ADD CONSTRAINT ck_fd_status "
        "CHECK (status IN ('ACTIVE', 'MATURED', 'CLOSED'))"
    )
    op.execute("ALTER TABLE fixed_deposits DROP CONSTRAINT IF EXISTS ck_fd_positive_principal")
    op.execute(
        "ALTER TABLE fixed_deposits ADD CONSTRAINT ck_fd_positive_principal "
        "CHECK (principal_minor > 0)"
    )
    op.execute("ALTER TABLE fixed_deposits DROP CONSTRAINT IF EXISTS ck_fd_positive_tenure")
    op.execute(
        "ALTER TABLE fixed_deposits ADD CONSTRAINT ck_fd_positive_tenure CHECK (tenure_days > 0)"
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fixed_deposits_customer_id_fkey'
            ) THEN
                ALTER TABLE fixed_deposits ADD CONSTRAINT fixed_deposits_customer_id_fkey
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fixed_deposits_transaction_id_fkey'
            ) THEN
                ALTER TABLE fixed_deposits ADD CONSTRAINT fixed_deposits_transaction_id_fkey
                FOREIGN KEY (transaction_id) REFERENCES ledger_transactions(id)
                ON DELETE RESTRICT;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fixed_deposits_customer_id ON fixed_deposits(customer_id)"
    )

    # ── 8. interest_accruals table ───────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interest_accruals (
            id SERIAL PRIMARY KEY,
            account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
            transaction_id UUID NOT NULL REFERENCES ledger_transactions(id) ON DELETE RESTRICT,
            period_month VARCHAR(7) NOT NULL,
            amount_minor BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_interest_accrual_period UNIQUE (account_id, period_month)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_interest_accruals_account_id ON interest_accruals(account_id)"
    )

    # ── 9. notification_logs table ───────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_logs (
            id SERIAL PRIMARY KEY,
            customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
            channel VARCHAR(10) NOT NULL,
            recipient VARCHAR(200) NOT NULL,
            subject VARCHAR(200) NOT NULL DEFAULT '',
            body TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'SIMULATED',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notification_logs_customer_id ON notification_logs(customer_id)"
    )

    # ── 10. System ledger accounts for new types ─────────────────────────────
    bind.execute(
        sa.text(
            """
            INSERT INTO ledger_accounts (id, code, account_type, account_id)
            VALUES
              (gen_random_uuid(), 'SYSTEM:INTEREST_EXPENSE', 'INTEREST_EXPENSE', NULL),
              (gen_random_uuid(), 'SYSTEM:LOAN_RECEIVABLE', 'LOAN_RECEIVABLE', NULL),
              (gen_random_uuid(), 'SYSTEM:FD_LIABILITY', 'FD_LIABILITY', NULL)
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade():
    # Drop new tables
    op.execute("DROP TABLE IF EXISTS interest_accruals")
    op.execute("DROP TABLE IF EXISTS loan_repayments")
    op.execute("DROP TABLE IF EXISTS fixed_deposits")
    op.execute("DROP TABLE IF EXISTS loans")
    op.execute("DROP TABLE IF EXISTS notification_logs")

    # Revert accounts columns
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS account_type")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS interest_rate_annual")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS daily_withdrawal_limit_minor")

    # Revert customers columns
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS email")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS address_line1")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS address_city")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS address_pin")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS kyc_status")

    # Revert ledger check constraints
    op.execute(
        "ALTER TABLE ledger_transactions DROP CONSTRAINT IF EXISTS ck_ledger_transaction_kind"
    )
    op.execute(
        "ALTER TABLE ledger_transactions ADD CONSTRAINT ck_ledger_transaction_kind "
        "CHECK (kind IN ('OPENING_DEPOSIT', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', "
        "'ACCOUNT_STATUS', 'REVERSAL'))"
    )
    op.execute(
        "ALTER TABLE ledger_accounts DROP CONSTRAINT IF EXISTS ck_ledger_account_type"
    )
    op.execute(
        "ALTER TABLE ledger_accounts ADD CONSTRAINT ck_ledger_account_type "
        "CHECK (account_type IN ('CUSTOMER_DEPOSIT', 'CASH_CLEARING'))"
    )
