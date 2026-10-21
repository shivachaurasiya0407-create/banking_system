import hashlib
import hmac
import json
import secrets
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from banking_api.models import (
    Account,
    AuditEvent,
    Branch,
    Customer,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
)
from banking_api.settings import Settings

IFSC = "SHIV0000001"
MIN_OPENING_BALANCE_MINOR = 200_000
CLEARING_ACCOUNT_CODE = "SYSTEM:CASH_CLEARING"


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

    def open_account(
        self, actor_id, idempotency_key, customer_data, opening_deposit,
        branch_ifsc=IFSC,
    ):
        amount = amount_to_minor_units(opening_deposit)
        if amount < MIN_OPENING_BALANCE_MINOR:
            raise BankingError("Opening deposit must be at least Rs. 2000.00.")
        identity_number = str(customer_data["identity_number"]).strip()
        if len(identity_number) != 12 or not identity_number.isdigit():
            raise BankingError("Identity number must contain exactly 12 digits.")
        request = {
            "customer": {
                key: customer_data[key]
                for key in (
                    "first_name",
                    "last_name",
                    "phone",
                    "age",
                    "country",
                    "state",
                )
            },
            "identity_fingerprint": self._fingerprint(identity_number),
            "opening_deposit_minor": amount,
            "branch_ifsc": branch_ifsc,
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
            customer = Customer(
                **request["customer"],
                identity_fingerprint=request["identity_fingerprint"],
            )
            self.session.add(customer)
            self.session.flush()
            account = self._new_account(customer.id, branch_ifsc)
            account.balance_minor = amount
            self.session.add(account)
            self.session.flush()
            customer_ledger = LedgerAccount(
                code=f"CUSTOMER:{account.id}",
                account_type="CUSTOMER_DEPOSIT",
                account_id=account.id,
            )
            clearing = self._get_clearing_account()
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
            clearing = self._get_clearing_account()
            if kind == "DEPOSIT":
                account.balance_minor += amount_minor
                postings = [(clearing, amount_minor), (customer_ledger, -amount_minor)]
            else:
                if amount_minor > account.balance_minor:
                    raise BankingError("Insufficient funds.")
                account.balance_minor -= amount_minor
                postings = [(customer_ledger, amount_minor), (clearing, -amount_minor)]
            self._post(transaction, postings)
            transaction.result_id = str(account.id)
            self._store_result(
                transaction, (account.account_number,), (account.balance_minor,)
            )
            self._audit(actor_id, kind.lower(), "account", account.id)
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

    def _begin_operation(self, actor_id, key, kind, request):
        if not key or len(key) > 128:
            raise BankingError("A valid Idempotency-Key header is required.")
        request_hash = hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
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

    def _get_clearing_account(self):
        clearing = self.session.scalar(
            select(LedgerAccount)
            .where(LedgerAccount.code == CLEARING_ACCOUNT_CODE)
            .with_for_update()
        )
        if clearing is None:
            clearing = LedgerAccount(
                code=CLEARING_ACCOUNT_CODE,
                account_type="CASH_CLEARING",
                account_id=None,
            )
            self.session.add(clearing)
            self.session.flush()
        return clearing

    def _new_account(self, customer_id, branch_ifsc=IFSC):
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
            account = Account(
                customer_id=customer_id,
                account_number=account_number,
                ifsc=branch_ifsc,
                branch_sequence=sequence,
                status="ACTIVE",
                balance_minor=0,
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
