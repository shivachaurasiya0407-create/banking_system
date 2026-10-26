import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class StaffUser(Base):
    __tablename__ = "staff_users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'TELLER', 'AUDITOR')", name="ck_staff_role"),
        CheckConstraint("failed_login_attempts >= 0", name="ck_staff_failed_attempts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active_session_id: Mapped[str | None] = mapped_column(String(36))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("age >= 18 AND age <= 110", name="ck_customer_age"),
        CheckConstraint(
            "kyc_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="ck_customer_kyc_status",
        ),
        UniqueConstraint("identity_fingerprint", name="uq_customer_identity_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    identity_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    # Extended profile / KYC fields
    email: Mapped[str | None] = mapped_column(String(200))
    address_line1: Mapped[str | None] = mapped_column(String(250))
    address_city: Mapped[str | None] = mapped_column(String(100))
    address_pin: Mapped[str | None] = mapped_column(String(10))
    kyc_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")
    loans: Mapped[list["Loan"]] = relationship(back_populates="customer")
    fixed_deposits: Mapped[list["FixedDeposit"]] = relationship(back_populates="customer")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'FROZEN', 'CLOSED')", name="ck_account_status"),
        CheckConstraint(
            "account_type IN ('SAVINGS', 'CURRENT', 'SALARY')",
            name="ck_account_type",
        ),
        CheckConstraint("balance_minor >= 0", name="ck_account_nonnegative_balance"),
        UniqueConstraint("account_number", name="uq_account_number"),
        UniqueConstraint("ifsc", "branch_sequence", name="uq_account_branch_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_number: Mapped[str] = mapped_column(String(10), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, default="SAVINGS")
    ifsc: Mapped[str] = mapped_column(String(20), nullable=False)
    branch_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    balance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Annual interest rate % (e.g. 3.5000 for 3.5%)
    interest_rate_annual: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default=text("3.5000")
    )
    # Daily withdrawal limit in minor units; 0 means no limit
    daily_withdrawal_limit_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    customer: Mapped[Customer] = relationship(back_populates="accounts")
    interest_accruals: Mapped[list["InterestAccrual"]] = relationship(
        back_populates="account"
    )


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('OPENING_DEPOSIT', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', "
            "'ACCOUNT_STATUS', 'REVERSAL', 'INTEREST', 'LOAN_DISBURSEMENT', "
            "'LOAN_REPAYMENT', 'FD_OPEN', 'FD_MATURITY', 'FD_PREMATURE_CLOSURE')",
            name="ck_ledger_transaction_kind",
        ),
        CheckConstraint("status IN ('PENDING', 'POSTED', 'REVERSED')", name="ck_ledger_status"),
        UniqueConstraint("actor_id", "idempotency_key", name="uq_actor_idempotency_key"),
        Index("ix_ledger_transactions_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    memo: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    result_id: Mapped[str | None] = mapped_column(String(200))
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT")
    )
    result_payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="transaction")


Index(
    "uq_ledger_transactions_reversal_of",
    LedgerTransaction.reversal_of_id,
    unique=True,
    postgresql_where=text("reversal_of_id IS NOT NULL"),
    sqlite_where=text("reversal_of_id IS NOT NULL"),
)


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('CUSTOMER_DEPOSIT', 'CASH_CLEARING', 'INTEREST_EXPENSE', "
            "'LOAN_RECEIVABLE', 'FD_LIABILITY')",
            name="ck_ledger_account_type",
        ),
        UniqueConstraint("account_id", name="uq_ledger_account_customer_account"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint(
            "next_sequence BETWEEN 1 AND 1000000",
            name="ck_branch_sequence_range",
        ),
    )

    ifsc: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    next_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount_minor <> 0", name="ck_ledger_entry_nonzero"),
        Index("ix_ledger_entries_account", "ledger_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    ledger_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transaction: Mapped[LedgerTransaction] = relationship(back_populates="entries")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        server_default=text("'{}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ─── New real-bank models ────────────────────────────────────────────────────


class Loan(Base):
    """Loan account — tracks principal, outstanding balance, and EMI schedule."""

    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint(
            "loan_type IN ('PERSONAL', 'HOME', 'VEHICLE', 'EDUCATION', 'GOLD')",
            name="ck_loan_type",
        ),
        CheckConstraint(
            "status IN ('APPLIED', 'APPROVED', 'ACTIVE', 'CLOSED', 'REJECTED', 'DEFAULTED')",
            name="ck_loan_status",
        ),
        CheckConstraint("principal_minor > 0", name="ck_loan_positive_principal"),
        CheckConstraint("tenure_months > 0", name="ck_loan_positive_tenure"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Linked savings/current account for EMI debit
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    loan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="APPLIED")
    principal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    outstanding_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interest_rate_annual: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    emi_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_emi_date: Mapped["Date | None"] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    memo: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    customer: Mapped[Customer] = relationship(back_populates="loans")
    repayments: Mapped[list["LoanRepayment"]] = relationship(back_populates="loan")


class LoanRepayment(Base):
    """Individual EMI / part-payment recorded against a loan."""

    __tablename__ = "loan_repayments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    loan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    principal_component_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interest_component_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    loan: Mapped[Loan] = relationship(back_populates="repayments")


class FixedDeposit(Base):
    """Fixed deposit (FD) account linked to a customer."""

    __tablename__ = "fixed_deposits"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'MATURED', 'CLOSED')",
            name="ck_fd_status",
        ),
        CheckConstraint("principal_minor > 0", name="ck_fd_positive_principal"),
        CheckConstraint("tenure_days > 0", name="ck_fd_positive_tenure"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Source account for FD funds
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    principal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interest_rate_annual: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    tenure_days: Mapped[int] = mapped_column(Integer, nullable=False)
    maturity_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    # Maturity amount = principal + interest
    maturity_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Premature closure penalty rate %
    premature_penalty_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default=text("1.0000")
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    customer: Mapped[Customer] = relationship(back_populates="fixed_deposits")


class InterestAccrual(Base):
    """Monthly interest credit record for savings accounts."""

    __tablename__ = "interest_accruals"
    __table_args__ = (
        UniqueConstraint("account_id", "period_month", name="uq_interest_accrual_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    period_month: Mapped[str] = mapped_column(
        String(7), nullable=False
    )  # e.g. "2025-10"
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    account: Mapped[Account] = relationship(back_populates="interest_accruals")


class NotificationLog(Base):
    """Log of all notifications (SMS/Email) sent to customers."""

    __tablename__ = "notification_logs"
    __table_args__ = (Index("ix_notification_logs_customer_id", "customer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # SMS | EMAIL
    recipient: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SIMULATED"
    )  # SIMULATED | SENT | FAILED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
