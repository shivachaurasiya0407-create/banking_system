import datetime
import hashlib
import hmac
import json
import math
import secrets
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from banking_api.models import (
    Account,
    AuditEvent,
    Branch,
    Customer,
    FixedDeposit,
    InterestAccrual,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    Loan,
    LoanRepayment,
    NotificationLog,
)
from banking_api.settings import Settings

IFSC = "SHIV0000001"
MIN_OPENING_BALANCE_MINOR = 200_000  # Rs. 2000
CLEARING_ACCOUNT_CODE = "SYSTEM:CASH_CLEARING"
INTEREST_EXPENSE_CODE = "SYSTEM:INTEREST_EXPENSE"
SAVINGS_DAILY_WITHDRAWAL_LIMIT_MINOR = 50_000_000
LOAN_RECEIVABLE_CODE = "SYSTEM:LOAN_RECEIVABLE"
FD_LIABILITY_CODE = "SYSTEM:FD_LIABILITY"


class BankingError(ValueError):
    pass


class IdempotencyConflict(BankingError):
    pass


@dataclass(frozen=True)
class OperationResult:
    transaction_id: uuid.UUID
    account_numbers: tuple[str, ...]
    balances_minor: tuple[int, ...]
    replayed: bool = False


def amount_to_minor_units(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BankingError("Amount must be a valid decimal number.") from None
    if not amount.is_finite() or amount <= 0:
        raise BankingError("Amount must be a finite number greater than zero.")
    if amount != amount.quantize(Decimal("0.01")):
        raise BankingError("Amount must not have more than two decimal places.")
    return int(amount * 100)


def _calculate_emi(principal_minor: int, annual_rate: Decimal, tenure_months: int) -> int:
    """Calculate EMI using standard reducing-balance formula.

    Returns EMI in minor units (paise), rounded up to the nearest rupee.
    """
    if annual_rate == 0:
        return math.ceil(principal_minor / tenure_months)
    monthly_rate = float(annual_rate) / (12 * 100)
    factor = (1 + monthly_rate) ** tenure_months
    emi_exact = principal_minor * monthly_rate * factor / (factor - 1)
    return math.ceil(emi_exact)  # round up to protect bank


def _fd_maturity_amount(principal_minor: int, annual_rate: Decimal, tenure_days: int) -> int:
    """Simple-interest FD maturity: P + P*R*T/365, in minor units."""
    interest = Decimal(principal_minor) * annual_rate * Decimal(tenure_days) / Decimal(365 * 100)
    return principal_minor + int(interest.to_integral_value(ROUND_HALF_UP))


class BankingService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings

    @contextmanager
    def _atomic(self):
        if self.session.in_transaction():
            with self.session.begin_nested():
                yield
        else:
            with self.session.begin():
                yield

    # ─── Account Operations ────────────────────────────────────────────────

    def open_account(
        self, actor_id, idempotency_key, customer_data, opening_deposit,
        branch_ifsc=IFSC, account_type="SAVINGS",
    ):
        amount = amount_to_minor_units(opening_deposit)
        if amount < MIN_OPENING_BALANCE_MINOR:
            raise BankingError("Opening deposit must be at least Rs. 2000.00.")
        identity_number = str(customer_data["identity_number"]).strip()
        if len(identity_number) != 12 or not identity_number.isdigit():
            raise BankingError("Identity number must contain exactly 12 digits.")
        if account_type not in {"SAVINGS", "CURRENT", "SALARY"}:
            raise BankingError("Account type must be SAVINGS, CURRENT, or SALARY.")
        request = {
            "customer": {
                key: customer_data.get(key)
                for key in (
                    "first_name", "last_name", "phone", "age", "country", "state",
                )
            },
            "identity_fingerprint": self._fingerprint(identity_number),
            "opening_deposit_minor": amount,
            "branch_ifsc": branch_ifsc,
            "account_type": account_type,
        }
        with self._atomic():
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, "OPENING_DEPOSIT", request
            )
            if replay:
                return self._replayed_result(transaction)
            existing_customer = self.session.scalar(
                select(Customer).where(
                    Customer.identity_fingerprint == request["identity_fingerprint"]
                )
            )
            if existing_customer is not None:
                raise BankingError("A customer with this identity is already registered.")
            customer_fields = dict(request["customer"])
            # Optional extended fields
            for field in ("email", "address_line1", "address_city", "address_pin"):
                val = customer_data.get(field)
                if val:
                    customer_fields[field] = val
            customer = Customer(
                **customer_fields,
                identity_fingerprint=request["identity_fingerprint"],
            )
            self.session.add(customer)
            self.session.flush()
            account = self._new_account(customer.id, branch_ifsc, account_type)
            account.balance_minor = amount
            self.session.add(account)
            self.session.flush()
            customer_ledger = LedgerAccount(
                code=f"CUSTOMER:{account.id}",
                account_type="CUSTOMER_DEPOSIT",
                account_id=account.id,
            )
            clearing = self._get_system_ledger(CLEARING_ACCOUNT_CODE)
            self.session.add(customer_ledger)
            self.session.flush()
            self._post(
                transaction,
                [
                    (clearing, amount),
                    (customer_ledger, -amount),
                ],
            )
            transaction.result_id = str(account.id)
            self._store_result(
                transaction,
                (account.account_number,),
                (account.balance_minor,),
            )
            self._audit(actor_id, "account.open", "account", account.id)
            self._notify(
                customer.id,
                customer.phone,
                "SMS",
                f"Dear {customer.first_name}, your SHIVA Bank {account_type} account "
                f"{account.account_number} has been opened. Opening balance: "
                f"Rs.{amount / 100:.2f}.",
            )
            return OperationResult(
                transaction.id, (account.account_number,), (account.balance_minor,)
            )

    def change_balance(self, actor_id, idempotency_key, account_number, kind, amount, memo=""):
        if kind not in {"DEPOSIT", "WITHDRAWAL"}:
            raise BankingError("Unsupported balance operation.")
        amount_minor = amount_to_minor_units(amount)
        request = {
            "account_number": account_number,
            "kind": kind,
            "amount_minor": amount_minor,
        }
        if memo:
            request["memo"] = memo.strip()
        with self._atomic():
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, kind, request
            )
            if replay:
                return self._replayed_result(transaction)
            if memo:
                transaction.memo = memo.strip()[:250]
            account = self._get_account(account_number, lock=True)
            if account.status != "ACTIVE":
                raise BankingError("Account is not active.")
            customer_ledger = self._customer_ledger(account.id)
            clearing = self._get_system_ledger(CLEARING_ACCOUNT_CODE)
            if kind == "DEPOSIT":
                account.balance_minor += amount_minor
                postings = [(clearing, amount_minor), (customer_ledger, -amount_minor)]
            else:
                if amount_minor > account.balance_minor:
                    raise BankingError("Insufficient funds.")
                # Daily withdrawal limit check
                withdrawal_limit = self._effective_daily_withdrawal_limit(account)
                if withdrawal_limit > 0:
                    today_withdrawn = self._today_withdrawn(account.id)
                    if today_withdrawn + amount_minor > withdrawal_limit:
                        raise BankingError(
                            f"Daily withdrawal limit of Rs."
                            f"{withdrawal_limit / 100:.2f} exceeded."
                        )
                account.balance_minor -= amount_minor
                postings = [(customer_ledger, amount_minor), (clearing, -amount_minor)]
            self._post(transaction, postings)
            transaction.result_id = str(account.id)
            self._store_result(
                transaction, (account.account_number,), (account.balance_minor,)
            )
            self._audit(actor_id, kind.lower(), "account", account.id)
            customer = self.session.get(Customer, account.customer_id)
            if customer:
                action_word = "credited" if kind == "DEPOSIT" else "debited"
                self._notify(
                    customer.id,
                    customer.phone,
                    "SMS",
                    f"Rs.{amount_minor / 100:.2f} {action_word} in A/c "
                    f"{account.account_number}. Balance: Rs.{account.balance_minor / 100:.2f}."
                    + (f" Ref: {memo}" if memo else ""),
                )
            return OperationResult(
                transaction.id, (account.account_number,), (account.balance_minor,)
            )

    def transfer(self, actor_id, idempotency_key, sender_number, receiver_number, amount, memo=""):
        amount_minor = amount_to_minor_units(amount)
        if sender_number == receiver_number:
            raise BankingError("Sender and receiver must be different accounts.")
        request = {
            "sender_number": sender_number,
            "receiver_number": receiver_number,
            "amount_minor": amount_minor,
        }
        if memo:
            request["memo"] = memo.strip()
        with self._atomic():
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, "TRANSFER", request
            )
            if replay:
                return self._replayed_result(transaction)
            if memo:
                transaction.memo = memo.strip()[:250]

            locked_accounts = self.session.scalars(
                select(Account)
                .where(Account.account_number.in_([sender_number, receiver_number]))
                .order_by(Account.account_number)
                .with_for_update()
            ).all()
            by_number = {account.account_number: account for account in locked_accounts}
            sender = by_number.get(sender_number)
            receiver = by_number.get(receiver_number)
            if sender is None or receiver is None:
                raise BankingError("Sender or receiver account was not found.")
            if sender.status != "ACTIVE" or receiver.status != "ACTIVE":
                raise BankingError("Both accounts must be active.")
            if sender.balance_minor < amount_minor:
                raise BankingError("Insufficient funds.")
            # Daily limit check for sender
            withdrawal_limit = self._effective_daily_withdrawal_limit(sender)
            if withdrawal_limit > 0:
                today_withdrawn = self._today_withdrawn(sender.id)
                if today_withdrawn + amount_minor > withdrawal_limit:
                    raise BankingError(
                        f"Daily transfer limit of Rs."
                        f"{withdrawal_limit / 100:.2f} exceeded."
                    )
            sender.balance_minor -= amount_minor
            receiver.balance_minor += amount_minor
            sender_ledger = self._customer_ledger(sender.id)
            receiver_ledger = self._customer_ledger(receiver.id)
            self._post(
                transaction,
                [(sender_ledger, amount_minor), (receiver_ledger, -amount_minor)],
            )
            transaction.result_id = json.dumps([str(sender.id), str(receiver.id)])
            self._store_result(
                transaction,
                (sender_number, receiver_number),
                (sender.balance_minor, receiver.balance_minor),
            )
            self._audit(
                actor_id,
                "account.transfer",
                "ledger_transaction",
                transaction.id,
                {"sender": sender_number, "receiver": receiver_number},
            )
            # Notifications
            sender_customer = self.session.get(Customer, sender.customer_id)
            if sender_customer:
                self._notify(
                    sender_customer.id,
                    sender_customer.phone,
                    "SMS",
                    f"Rs.{amount_minor / 100:.2f} debited from A/c {sender_number} "
                    f"(Transfer to {receiver_number}). Balance: Rs.{sender.balance_minor / 100:.2f}.",
                )
            return OperationResult(
                transaction.id,
                (sender_number, receiver_number),
                (sender.balance_minor, receiver.balance_minor),
            )

    def set_account_status(
        self, actor_id, idempotency_key, account_number, new_status
    ):
        if new_status not in {"ACTIVE", "FROZEN", "CLOSED"}:
            raise BankingError("Unsupported account status.")
        request = {"account_number": account_number, "status": new_status}
        with self._atomic():
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, "ACCOUNT_STATUS", request
            )
            if replay:
                return self._replayed_result(transaction)
            account = self._get_account(account_number, lock=True)
            if account.status == new_status:
                raise BankingError(f"Account is already {new_status.lower()}.")
            if account.status == "CLOSED" or (
                new_status == "CLOSED" and account.balance_minor != 0
            ):
                raise BankingError("Only zero-balance accounts may be closed.")
            account.status = new_status
            transaction.result_id = str(account.id)
            self._post(transaction, [])
            self._store_result(
                transaction, (account.account_number,), (account.balance_minor,)
            )
            self._audit(
                actor_id, "account.status", "account", account.id, {"status": new_status}
            )
            return OperationResult(
                transaction.id, (account.account_number,), (account.balance_minor,)
            )

    def reverse_transaction(self, actor_id, idempotency_key, original_id, reason):
        original_id = uuid.UUID(str(original_id))
        reason = str(reason).strip()
        if not reason or len(reason) > 250:
            raise BankingError("A reversal reason of at most 250 characters is required.")
        request = {"original_transaction_id": str(original_id), "reason": reason}
        with self._atomic():
            reversal, replay = self._begin_operation(
                actor_id, idempotency_key, "REVERSAL", request
            )
            if replay:
                return self._replayed_result(reversal)
            original = self.session.scalar(
                select(LedgerTransaction)
                .where(LedgerTransaction.id == original_id)
                .with_for_update()
            )
            if original is None:
                raise BankingError("Transaction to reverse was not found.")
            if original.status != "POSTED" or original.kind in {"ACCOUNT_STATUS", "REVERSAL"}:
                raise BankingError("Only posted money transactions can be reversed.")
            if original.actor_id == actor_id:
                raise BankingError("A different staff member must approve the reversal.")
            entries = self.session.execute(
                select(LedgerEntry, LedgerAccount)
                .join(LedgerAccount, LedgerEntry.ledger_account_id == LedgerAccount.id)
                .where(LedgerEntry.transaction_id == original.id)
                .order_by(LedgerAccount.id)
            ).all()
            if len(entries) < 2 or sum(entry.amount_minor for entry, _ in entries) != 0:
                raise BankingError("The original transaction has invalid ledger postings.")

            account_ids = [
                ledger_account.account_id
                for _, ledger_account in entries
                if ledger_account.account_type == "CUSTOMER_DEPOSIT"
            ]
            accounts = self.session.scalars(
                select(Account)
                .where(Account.id.in_(account_ids))
                .order_by(Account.id)
                .with_for_update()
            ).all()
            account_by_id = {account.id: account for account in accounts}
            for entry, ledger_account in entries:
                if ledger_account.account_type == "CUSTOMER_DEPOSIT":
                    account = account_by_id.get(ledger_account.account_id)
                    if account is None:
                        raise BankingError("A customer account for this ledger entry is missing.")
                    if account.status != "ACTIVE":
                        raise BankingError("Only active accounts can be affected by a reversal.")
                    account.balance_minor += entry.amount_minor
                    if account.balance_minor < 0:
                        raise BankingError("Reversal would produce a negative account balance.")

            reversal.kind = "REVERSAL"
            reversal.reversal_of_id = original.id
            reversal.memo = reason
            original.status = "REVERSED"
            reversal_entries = [
                (ledger_account, -entry.amount_minor)
                for entry, ledger_account in entries
            ]
            self._post(reversal, reversal_entries)
            result_accounts = tuple(account.account_number for account in accounts)
            result_balances = tuple(account.balance_minor for account in accounts)
            self._store_result(reversal, result_accounts, result_balances)
            reversal.result_id = str(original.id)
            self._audit(
                actor_id,
                "ledger.transaction_reversed",
                "ledger_transaction",
                original.id,
                {"reversal_id": str(reversal.id), "reason": reason},
            )
            return OperationResult(
                reversal.id, result_accounts, result_balances
            )

    # ─── Loan Operations ──────────────────────────────────────────────────

    def apply_loan(self, actor_id, account_number, loan_type, principal_amount,
                   interest_rate_annual, tenure_months, memo=""):
        """Create a new loan application (status=APPLIED)."""
        principal_minor = amount_to_minor_units(principal_amount)
        if principal_minor < 100_000:  # min Rs.1000
            raise BankingError("Minimum loan amount is Rs. 1000.")
        account = self._get_account(account_number, lock=False)
        if account.status != "ACTIVE":
            raise BankingError("Linked account must be active.")
        emi_minor = _calculate_emi(principal_minor, Decimal(str(interest_rate_annual)), tenure_months)
        loan = Loan(
            customer_id=account.customer_id,
            account_id=account.id,
            loan_type=loan_type,
            principal_minor=principal_minor,
            outstanding_minor=principal_minor,
            interest_rate_annual=Decimal(str(interest_rate_annual)),
            tenure_months=tenure_months,
            emi_minor=emi_minor,
            memo=memo.strip()[:500],
        )
        self.session.add(loan)
        self.session.flush()
        self._audit(actor_id, "loan.applied", "loan", loan.id,
                    {"type": loan_type, "principal": principal_minor})
        customer = self.session.get(Customer, account.customer_id)
        if customer:
            self._notify(
                customer.id, customer.phone, "SMS",
                f"Your {loan_type} loan application of Rs.{principal_minor / 100:.2f} "
                f"has been received. Loan ID: {str(loan.id)[:8].upper()}.",
            )
        return loan

    def action_loan(self, actor_id, idempotency_key, loan_id, action, memo=""):
        """Approve, reject, or disburse a loan."""
        loan = self.session.scalar(
            select(Loan).where(Loan.id == loan_id).with_for_update()
        )
        if loan is None:
            raise BankingError("Loan not found.")
        if action == "APPROVE":
            if loan.status != "APPLIED":
                raise BankingError("Only APPLIED loans can be approved.")
            loan.status = "APPROVED"
            loan.approved_by_id = actor_id
            if memo:
                loan.memo = (loan.memo + " | " + memo).strip()[:500]
            self.session.flush()
            self._audit(actor_id, "loan.approved", "loan", loan.id)
            return {"loan_id": str(loan.id), "status": loan.status}
        elif action == "REJECT":
            if loan.status not in {"APPLIED", "APPROVED"}:
                raise BankingError("Only APPLIED or APPROVED loans can be rejected.")
            loan.status = "REJECTED"
            if memo:
                loan.memo = (loan.memo + " | " + memo).strip()[:500]
            self.session.flush()
            self._audit(actor_id, "loan.rejected", "loan", loan.id)
            return {"loan_id": str(loan.id), "status": loan.status}
        elif action == "DISBURSE":
            if loan.status != "APPROVED":
                raise BankingError("Only APPROVED loans can be disbursed.")
            # Disburse = credit principal to linked account
            with self._atomic():
                transaction, replay = self._begin_operation(
                    actor_id, idempotency_key, "LOAN_DISBURSEMENT",
                    {"loan_id": str(loan.id), "amount_minor": loan.principal_minor},
                )
                if not replay:
                    account = self.session.scalar(
                        select(Account).where(Account.id == loan.account_id).with_for_update()
                    )
                    if account is None or account.status != "ACTIVE":
                        raise BankingError("Linked account is not active.")
                    account.balance_minor += loan.principal_minor
                    customer_ledger = self._customer_ledger(account.id)
                    loan_ledger = self._get_system_ledger(LOAN_RECEIVABLE_CODE)
                    self._post(
                        transaction,
                        [(loan_ledger, loan.principal_minor), (customer_ledger, -loan.principal_minor)],
                    )
                    transaction.result_id = str(loan.id)
                    self._store_result(
                        transaction, (account.account_number,), (account.balance_minor,)
                    )
                    loan.status = "ACTIVE"
                    loan.disbursed_at = datetime.datetime.now(datetime.UTC)
                    loan.next_emi_date = (
                        datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
                    ).date()
                    self._audit(actor_id, "loan.disbursed", "loan", loan.id)
                    customer = self.session.get(Customer, loan.customer_id)
                    if customer:
                        self._notify(
                            customer.id, customer.phone, "SMS",
                            f"Rs.{loan.principal_minor / 100:.2f} disbursed to your account "
                            f"{account.account_number}. Monthly EMI: Rs.{loan.emi_minor / 100:.2f}.",
                        )
            return {"loan_id": str(loan.id), "status": loan.status,
                    "emi_minor": loan.emi_minor}
        else:
            raise BankingError(f"Unknown loan action: {action}")

    def repay_loan(self, actor_id, idempotency_key, loan_id, amount, memo=""):
        """Post an EMI/repayment against an active loan."""
        amount_minor = amount_to_minor_units(amount)
        with self._atomic():
            loan = self.session.scalar(
                select(Loan).where(Loan.id == loan_id).with_for_update()
            )
            if loan is None:
                raise BankingError("Loan not found.")
            if loan.status != "ACTIVE":
                raise BankingError("Only ACTIVE loans accept repayments.")
            if amount_minor > loan.outstanding_minor:
                raise BankingError("Repayment exceeds outstanding balance.")
            account = self.session.scalar(
                select(Account).where(Account.id == loan.account_id).with_for_update()
            )
            if account is None or account.status != "ACTIVE":
                raise BankingError("Linked account is not active.")
            if account.balance_minor < amount_minor:
                raise BankingError("Insufficient funds in linked account for EMI.")
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, "LOAN_REPAYMENT",
                {"loan_id": str(loan_id), "amount_minor": amount_minor},
            )
            if replay:
                return self._replayed_result(transaction)
            # Split principal vs interest (simple apportionment)
            monthly_rate = float(loan.interest_rate_annual) / (12 * 100)
            interest_component = int(loan.outstanding_minor * monthly_rate)
            principal_component = min(amount_minor - interest_component, loan.outstanding_minor)
            if principal_component < 0:
                principal_component = 0
                interest_component = amount_minor
            account.balance_minor -= amount_minor
            loan.outstanding_minor -= principal_component
            if loan.outstanding_minor <= 0:
                loan.outstanding_minor = 0
                loan.status = "CLOSED"
                loan.closed_at = datetime.datetime.now(datetime.UTC)
            else:
                loan.next_emi_date = (
                    datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
                ).date()
            customer_ledger = self._customer_ledger(account.id)
            loan_ledger = self._get_system_ledger(LOAN_RECEIVABLE_CODE)
            self._post(
                transaction,
                [(customer_ledger, amount_minor), (loan_ledger, -amount_minor)],
            )
            transaction.memo = memo.strip()[:250] if memo else "EMI Repayment"
            transaction.result_id = str(loan.id)
            self._store_result(transaction, (account.account_number,), (account.balance_minor,))
            repayment = LoanRepayment(
                loan_id=loan.id,
                transaction_id=transaction.id,
                amount_minor=amount_minor,
                principal_component_minor=principal_component,
                interest_component_minor=interest_component,
            )
            self.session.add(repayment)
            self._audit(actor_id, "loan.repayment", "loan", loan.id,
                        {"amount": amount_minor, "outstanding": loan.outstanding_minor})
            return OperationResult(
                transaction.id, (account.account_number,), (account.balance_minor,)
            )

    # ─── Fixed Deposit Operations ─────────────────────────────────────────

    def open_fd(self, actor_id, idempotency_key, account_number,
                principal_amount, interest_rate_annual, tenure_days):
        """Debit account and open FD."""
        principal_minor = amount_to_minor_units(principal_amount)
        if principal_minor < 100_000:  # min Rs.1000
            raise BankingError("Minimum FD amount is Rs. 1000.")
        rate = Decimal(str(interest_rate_annual))
        maturity_amount = _fd_maturity_amount(principal_minor, rate, tenure_days)
        with self._atomic():
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, "FD_OPEN",
                {"account_number": account_number, "principal_minor": principal_minor,
                 "tenure_days": tenure_days},
            )
            if replay:
                return self._replayed_result(transaction)
            account = self._get_account(account_number, lock=True)
            if account.status != "ACTIVE":
                raise BankingError("Source account must be active.")
            if account.balance_minor < principal_minor:
                raise BankingError("Insufficient funds for FD.")
            account.balance_minor -= principal_minor
            customer_ledger = self._customer_ledger(account.id)
            fd_ledger = self._get_system_ledger(FD_LIABILITY_CODE)
            self._post(
                transaction,
                [(customer_ledger, principal_minor), (fd_ledger, -principal_minor)],
            )
            transaction.memo = f"FD opened for {tenure_days} days at {rate}% p.a."
            transaction.result_id = str(account.id)
            self._store_result(transaction, (account.account_number,), (account.balance_minor,))
            maturity_date = (
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=tenure_days)
            ).date()
            fd = FixedDeposit(
                customer_id=account.customer_id,
                account_id=account.id,
                principal_minor=principal_minor,
                interest_rate_annual=rate,
                tenure_days=tenure_days,
                maturity_date=maturity_date,
                maturity_amount_minor=maturity_amount,
                transaction_id=transaction.id,
            )
            self.session.add(fd)
            self.session.flush()
            self._audit(actor_id, "fd.opened", "fixed_deposit", fd.id,
                        {"principal": principal_minor, "tenure_days": tenure_days})
            customer = self.session.get(Customer, account.customer_id)
            if customer:
                self._notify(
                    customer.id, customer.phone, "SMS",
                    f"FD of Rs.{principal_minor / 100:.2f} opened. Matures on "
                    f"{maturity_date}. Maturity amount: Rs.{maturity_amount / 100:.2f}.",
                )
            return {
                "fd_id": str(fd.id),
                "maturity_date": str(maturity_date),
                "maturity_amount": f"{maturity_amount / 100:.2f}",
                "account_balance": f"{account.balance_minor / 100:.2f}",
            }

    def close_fd(self, actor_id, idempotency_key, fd_id, premature=False):
        """Mature or prematurely close an FD, crediting back to source account."""
        with self._atomic():
            fd = self.session.scalar(
                select(FixedDeposit).where(FixedDeposit.id == fd_id).with_for_update()
            )
            if fd is None:
                raise BankingError("Fixed deposit not found.")
            if fd.status != "ACTIVE":
                raise BankingError("Only ACTIVE fixed deposits can be closed.")
            today = datetime.date.today()
            if not premature and today < fd.maturity_date:
                raise BankingError(
                    f"FD matures on {fd.maturity_date}. Use premature=true for early closure."
                )
            kind = "FD_PREMATURE_CLOSURE" if premature else "FD_MATURITY"
            if premature:
                # Apply penalty: reduce effective rate by penalty %
                effective_rate = max(Decimal("0"), fd.interest_rate_annual - fd.premature_penalty_rate)
                actual_days = (today - fd.opened_at.date()).days or 1
                payout = _fd_maturity_amount(fd.principal_minor, effective_rate, actual_days)
            else:
                payout = fd.maturity_amount_minor
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, kind,
                {"fd_id": str(fd_id), "premature": premature},
            )
            if replay:
                return self._replayed_result(transaction)
            account = self.session.scalar(
                select(Account).where(Account.id == fd.account_id).with_for_update()
            )
            if account is None or account.status != "ACTIVE":
                raise BankingError("Source account is not active.")
            account.balance_minor += payout
            customer_ledger = self._customer_ledger(account.id)
            fd_ledger = self._get_system_ledger(FD_LIABILITY_CODE)
            interest_ledger = self._get_system_ledger(INTEREST_EXPENSE_CODE)
            interest_paid = payout - fd.principal_minor
            postings = [
                (fd_ledger, fd.principal_minor),
                (customer_ledger, -payout),
            ]
            if interest_paid > 0:
                postings.append((interest_ledger, interest_paid))
            # Make sure postings balance
            total = sum(a for _, a in postings)
            if total != 0:
                postings.append((self._get_system_ledger(CLEARING_ACCOUNT_CODE), -total))
            self._post(transaction, postings)
            transaction.memo = (
                f"FD {'premature closure' if premature else 'maturity'} — "
                f"payout Rs.{payout / 100:.2f}"
            )
            transaction.result_id = str(fd.id)
            self._store_result(transaction, (account.account_number,), (account.balance_minor,))
            fd.status = "CLOSED" if premature else "MATURED"
            fd.closed_at = datetime.datetime.now(datetime.UTC)
            self._audit(actor_id, "fd.closed", "fixed_deposit", fd.id,
                        {"premature": premature, "payout": payout})
            return {
                "fd_id": str(fd.id),
                "status": fd.status,
                "payout": f"{payout / 100:.2f}",
                "account_balance": f"{account.balance_minor / 100:.2f}",
            }

    # ─── Interest Engine ──────────────────────────────────────────────────

    def post_monthly_interest(self, actor_id, idempotency_key, account_number, period_month):
        """Post monthly savings interest for the given period (YYYY-MM)."""
        import re
        if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", period_month):
            raise BankingError("period_month must be in YYYY-MM format.")
        with self._atomic():
            account = self._get_account(account_number, lock=True)
            if account.status != "ACTIVE":
                raise BankingError("Account is not active.")
            if account.account_type not in {"SAVINGS", "SALARY"}:
                raise BankingError("Interest is only posted to SAVINGS/SALARY accounts.")
            # Check if already posted for this period
            existing = self.session.scalar(
                select(InterestAccrual).where(
                    InterestAccrual.account_id == account.id,
                    InterestAccrual.period_month == period_month,
                )
            )
            if existing is not None:
                raise BankingError(f"Interest already posted for period {period_month}.")
            # Simple interest: balance * rate / 12
            interest_minor = int(
                Decimal(account.balance_minor) * account.interest_rate_annual / Decimal(1200)
            )
            if interest_minor <= 0:
                raise BankingError("Calculated interest is zero. No posting made.")
            transaction, replay = self._begin_operation(
                actor_id, idempotency_key, "INTEREST",
                {"account_number": account_number, "period_month": period_month,
                 "interest_minor": interest_minor},
            )
            if replay:
                return self._replayed_result(transaction)
            account.balance_minor += interest_minor
            customer_ledger = self._customer_ledger(account.id)
            interest_ledger = self._get_system_ledger(INTEREST_EXPENSE_CODE)
            self._post(
                transaction,
                [(interest_ledger, interest_minor), (customer_ledger, -interest_minor)],
            )
            transaction.memo = f"Interest credit for {period_month}"
            transaction.result_id = str(account.id)
            self._store_result(transaction, (account.account_number,), (account.balance_minor,))
            accrual = InterestAccrual(
                account_id=account.id,
                transaction_id=transaction.id,
                period_month=period_month,
                amount_minor=interest_minor,
            )
            self.session.add(accrual)
            self._audit(actor_id, "interest.posted", "account", account.id,
                        {"period": period_month, "amount": interest_minor})
            return OperationResult(
                transaction.id, (account.account_number,), (account.balance_minor,)
            )

    # ─── Query helpers ─────────────────────────────────────────────────────

    def get_balance(self, account_number):
        account = self._get_account(account_number, lock=False)
        return account

    def get_transactions(
        self, account_number, limit=100, offset=0, start_at=None, end_at=None, kind=None
    ):
        account = self._get_account(account_number, lock=False)
        statement = (
            select(LedgerEntry, LedgerTransaction)
            .join(
                LedgerTransaction,
                LedgerEntry.transaction_id == LedgerTransaction.id,
            )
            .join(
                LedgerAccount,
                LedgerEntry.ledger_account_id == LedgerAccount.id,
            )
            .where(LedgerAccount.account_id == account.id)
        )
        if start_at is not None:
            statement = statement.where(LedgerTransaction.created_at >= start_at)
        if end_at is not None:
            statement = statement.where(LedgerTransaction.created_at <= end_at)
        if kind is not None:
            statement = statement.where(LedgerTransaction.kind == kind)
        statement = statement.order_by(
            LedgerTransaction.created_at.desc(), LedgerTransaction.id.desc()
        ).limit(limit).offset(offset)
        return account, self.session.execute(statement).all()

    def get_statement(
        self, account_number, limit=1000, offset=0, start_at=None, end_at=None, kind=None
    ):
        account = self._get_account(account_number, lock=False)
        running_balance = func.sum(-LedgerEntry.amount_minor).over(
            order_by=(
                LedgerTransaction.created_at,
                LedgerTransaction.id,
                LedgerEntry.id,
            )
        ).label("balance_minor")
        history = (
            select(
                LedgerEntry.id.label("entry_id"),
                LedgerEntry.amount_minor.label("amount_minor"),
                LedgerTransaction.id.label("transaction_id"),
                LedgerTransaction.kind.label("kind"),
                LedgerTransaction.status.label("status"),
                LedgerTransaction.memo.label("memo"),
                LedgerTransaction.created_at.label("created_at"),
                running_balance,
            )
            .join(
                LedgerTransaction,
                LedgerEntry.transaction_id == LedgerTransaction.id,
            )
            .join(
                LedgerAccount,
                LedgerEntry.ledger_account_id == LedgerAccount.id,
            )
            .where(LedgerAccount.account_id == account.id)
            .subquery()
        )
        statement = select(history)
        if start_at is not None:
            statement = statement.where(history.c.created_at >= start_at)
        if end_at is not None:
            statement = statement.where(history.c.created_at <= end_at)
        if kind is not None:
            statement = statement.where(history.c.kind == kind)
        statement = statement.order_by(
            history.c.created_at.desc(),
            history.c.transaction_id.desc(),
            history.c.entry_id.desc(),
        ).limit(limit).offset(offset)
        return account, self.session.execute(statement).all()

    def reconcile_ledger(self):
        accounts = self.session.execute(
            select(Account.id, Account.account_number, Account.balance_minor)
        ).all()
        ledger_balances = dict(
            self.session.execute(
                select(
                    LedgerAccount.account_id,
                    func.coalesce(func.sum(LedgerEntry.amount_minor), 0),
                )
                .outerjoin(LedgerEntry, LedgerEntry.ledger_account_id == LedgerAccount.id)
                .where(LedgerAccount.account_type == "CUSTOMER_DEPOSIT")
                .group_by(LedgerAccount.account_id)
            ).all()
        )
        discrepancies = []
        for account_id, account_number, balance_minor in accounts:
            ledger_minor = ledger_balances.pop(account_id, None)
            if ledger_minor is None:
                discrepancies.append({
                    "account_number": account_number,
                    "account_balance_minor": balance_minor,
                    "ledger_balance_minor": None,
                    "difference_minor": None,
                    "issue": "missing_customer_ledger",
                })
            elif balance_minor != -ledger_minor:
                discrepancies.append({
                    "account_number": account_number,
                    "account_balance_minor": balance_minor,
                    "ledger_balance_minor": -ledger_minor,
                    "difference_minor": balance_minor + ledger_minor,
                    "issue": "balance_mismatch",
                })
        for account_id, ledger_minor in ledger_balances.items():
            discrepancies.append({
                "account_number": None,
                "account_balance_minor": None,
                "ledger_balance_minor": -ledger_minor,
                "difference_minor": None,
                "issue": "orphan_customer_ledger",
            })
        ledger_total = self.session.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_minor), 0))
        )
        return {
            "account_count": len(accounts),
            "ledger_entry_total_minor": ledger_total,
            "balanced": ledger_total == 0 and not discrepancies,
            "discrepancies": discrepancies,
        }

    # ─── Private helpers ──────────────────────────────────────────────────

    def _today_withdrawn(self, account_id: uuid.UUID) -> int:
        """Return total amount withdrawn/transferred from account today (UTC, minor units)."""
        from sqlalchemy import Date, cast
        today = datetime.datetime.now(datetime.UTC).date()
        result = self.session.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_minor), 0))
            .join(LedgerTransaction, LedgerEntry.transaction_id == LedgerTransaction.id)
            .join(LedgerAccount, LedgerEntry.ledger_account_id == LedgerAccount.id)
            .where(
                LedgerAccount.account_id == account_id,
                LedgerAccount.account_type == "CUSTOMER_DEPOSIT",
                LedgerEntry.amount_minor > 0,  # debits are positive in double-entry
                func.date(LedgerTransaction.created_at) == today,
                LedgerTransaction.status == "POSTED",
                LedgerTransaction.kind.in_(["WITHDRAWAL", "TRANSFER"]),
            )
        )
        return result or 0

    @staticmethod
    def _effective_daily_withdrawal_limit(account: Account) -> int:
        configured_limit = account.daily_withdrawal_limit_minor
        if account.account_type == "SAVINGS":
            return min(
                configured_limit or SAVINGS_DAILY_WITHDRAWAL_LIMIT_MINOR,
                SAVINGS_DAILY_WITHDRAWAL_LIMIT_MINOR,
            )
        return configured_limit

    def _begin_operation(self, actor_id, key, kind, request):
        if not key or len(key) > 128:
            raise BankingError("A valid Idempotency-Key header is required.")
        request_hash = hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        transaction_id = uuid.uuid4()
        insert_function = (
            pg_insert
            if self.session.get_bind().dialect.name == "postgresql"
            else sqlite_insert
            if self.session.get_bind().dialect.name == "sqlite"
            else None
        )
        if insert_function is None:
            raise BankingError("The configured database backend is not supported.")
        insert_statement = (
            insert_function(LedgerTransaction)
            .values(
                id=transaction_id,
                actor_id=actor_id,
                idempotency_key=key,
                request_hash=request_hash,
                kind=kind,
                status="PENDING",
            )
            .on_conflict_do_nothing(
                index_elements=["actor_id", "idempotency_key"]
            )
            .returning(LedgerTransaction.id)
        )
        inserted_id = self.session.execute(insert_statement).scalar_one_or_none()
        if inserted_id is not None:
            return self.session.get(LedgerTransaction, inserted_id), False
        existing = self.session.scalar(
            select(LedgerTransaction)
            .where(
                LedgerTransaction.actor_id == actor_id,
                LedgerTransaction.idempotency_key == key,
            )
            .with_for_update()
        )
        if existing is None:
            raise BankingError("Could not safely resolve the idempotent operation.")
        if existing.request_hash != request_hash or existing.kind != kind:
            raise IdempotencyConflict(
                "This Idempotency-Key was already used for a different request."
            )
        if existing.status != "POSTED":
            raise BankingError("A previous operation with this key is incomplete.")
        return existing, True

    @staticmethod
    def _replayed_result(transaction):
        payload = transaction.result_payload
        if not payload:
            raise BankingError("Stored idempotency result is unavailable.")
        return OperationResult(
            transaction.id,
            tuple(payload["account_numbers"]),
            tuple(payload["balances_minor"]),
            True,
        )

    @staticmethod
    def _store_result(transaction, account_numbers, balances_minor):
        transaction.result_payload = {
            "account_numbers": list(account_numbers),
            "balances_minor": list(balances_minor),
        }

    def _post(self, transaction, entries):
        if sum(amount for _, amount in entries) != 0:
            raise BankingError("Ledger postings must balance to zero.")
        for ledger_account, amount in entries:
            if amount:
                self.session.add(
                    LedgerEntry(
                        transaction_id=transaction.id,
                        ledger_account_id=ledger_account.id,
                        amount_minor=amount,
                    )
                )
        transaction.status = "POSTED"
        self.session.flush()

    def _get_account(self, account_number, lock):
        statement = select(Account).where(Account.account_number == account_number)
        if lock:
            statement = statement.with_for_update()
        account = self.session.scalar(statement)
        if account is None:
            raise BankingError("Account not found.")
        return account

    def _customer_ledger(self, account_id):
        ledger = self.session.scalar(
            select(LedgerAccount).where(LedgerAccount.account_id == account_id)
        )
        if ledger is None:
            raise BankingError("Account ledger has not been initialized.")
        return ledger

    def _get_system_ledger(self, code: str) -> LedgerAccount:
        """Fetch (or lazily create) a system ledger account by code."""
        ledger = self.session.scalar(
            select(LedgerAccount).where(LedgerAccount.code == code).with_for_update()
        )
        if ledger is None:
            type_map = {
                CLEARING_ACCOUNT_CODE: "CASH_CLEARING",
                INTEREST_EXPENSE_CODE: "INTEREST_EXPENSE",
                LOAN_RECEIVABLE_CODE: "LOAN_RECEIVABLE",
                FD_LIABILITY_CODE: "FD_LIABILITY",
            }
            ledger = LedgerAccount(
                code=code,
                account_type=type_map.get(code, "CASH_CLEARING"),
                account_id=None,
            )
            self.session.add(ledger)
            self.session.flush()
        return ledger

    def _new_account(self, customer_id, branch_ifsc=IFSC, account_type="SAVINGS"):
        branch = self.session.scalar(
            select(Branch).where(Branch.ifsc == branch_ifsc).with_for_update()
        )
        if branch is None:
            raise BankingError("The configured branch has not been initialized.")
        if branch.next_sequence > 999_999:
            raise BankingError("The configured branch has exhausted its account sequence.")
        sequence = branch.next_sequence
        branch.next_sequence += 1
        for _ in range(20):
            account_number = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)
            if self.session.scalar(
                select(Account.id).where(Account.account_number == account_number)
            ):
                continue
            # Default interest rates by account type
            default_rate = {"SAVINGS": Decimal("3.5"), "SALARY": Decimal("3.5"), "CURRENT": Decimal("0")}.get(
                account_type, Decimal("3.5")
            )
            account = Account(
                customer_id=customer_id,
                account_number=account_number,
                account_type=account_type,
                ifsc=branch_ifsc,
                branch_sequence=sequence,
                status="ACTIVE",
                balance_minor=0,
                interest_rate_annual=default_rate,
            )
            self.session.add(account)
            self.session.flush()
            return account
        raise BankingError("Could not allocate a unique account number.")

    def _fingerprint(self, identity_number):
        return hmac.new(
            self.settings.pii_hmac_key.encode("utf-8"),
            identity_number.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    def _audit(self, actor_id, action, entity_type, entity_id, metadata=None):
        self.session.add(
            AuditEvent(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                metadata_json=metadata or {},
            )
        )

    def _notify(self, customer_id, recipient, channel, body, subject=""):
        """Log a simulated SMS/email notification."""
        self.session.add(
            NotificationLog(
                customer_id=customer_id,
                channel=channel,
                recipient=recipient,
                subject=subject,
                body=body,
                status="SIMULATED",
            )
        )
