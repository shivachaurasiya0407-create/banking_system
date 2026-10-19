import argparse
import csv
import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from banking_api.database import configure_database
from banking_api.models import (
    Account,
    Branch,
    Customer,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    StaffUser,
)
from banking_api.service import CLEARING_ACCOUNT_CODE
from banking_api.settings import Settings

NAMESPACE = uuid.UUID("df2b0820-a218-4e9e-b547-6b3f4ec5a8b3")
REQUIRED_ACCOUNT_FIELDS = {
    "Name", "Last_Name", "Phone", "Age", "Country", "State", "Aadhar",
    "Account_no", "Ifsc_number", "Balance", "Status",
}


class ImportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ImportReport:
    accounts: int
    customers: int
    transactions: int
    ledger_entries: int
    dry_run: bool


def _minor_units(value, label):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ImportValidationError(f"{label} is not a valid amount.") from None
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ImportValidationError(f"{label} must be a non-negative amount with at most two decimals.")
    return int(amount * 100)


def _read_csv(path):
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))
    except OSError as error:
        raise ImportValidationError(f"Could not read {path}: {error}") from None


def _transaction_kind(value):
    normalized = re.sub(r"[^a-z]", "", value.casefold())
    kinds = {
        "openingdeposit": "OPENING_DEPOSIT",
        "deposit": "DEPOSIT",
        "withdrawal": "WITHDRAWAL",
        "withdraw": "WITHDRAWAL",
        "transfer": "TRANSFER",
    }
    try:
        return kinds[normalized]
    except KeyError:
        raise ImportValidationError(f"Unsupported legacy transaction type: {value!r}.") from None


def _read_source(accounts_path, history_dir, pii_hmac_key):
    account_rows = _read_csv(accounts_path)
    if not account_rows:
        raise ImportValidationError("The accounts CSV is empty.")
    missing = REQUIRED_ACCOUNT_FIELDS - set(account_rows[0])
    if missing:
        raise ImportValidationError(f"Accounts CSV is missing columns: {', '.join(sorted(missing))}.")

    accounts = {}
    customer_by_fingerprint = {}
    for row_number, row in enumerate(account_rows, start=2):
        account_number = row["Account_no"].strip()
        if not re.fullmatch(r"[0-9]{10}", account_number):
            raise ImportValidationError(f"Invalid account number on CSV row {row_number}.")
        if account_number in accounts:
            raise ImportValidationError(f"Duplicate account number {account_number}.")
        identity_number = row["Aadhar"].strip()
        if not re.fullmatch(r"[0-9]{12}", identity_number):
            raise ImportValidationError(f"Invalid identity number for account {account_number}.")
        fingerprint = hmac.new(
            pii_hmac_key.encode("utf-8"), identity_number.encode("ascii"), hashlib.sha256
        ).hexdigest()
        status = row["Status"].strip().casefold()
        statuses = {
            "active": "ACTIVE",
            "unfrozen": "ACTIVE",
            "frozen": "FROZEN",
            "closed": "CLOSED",
        }
        if status not in statuses:
            raise ImportValidationError(f"Unsupported status {row['Status']!r} for account {account_number}.")
        try:
            age = int(row["Age"])
        except ValueError:
            raise ImportValidationError(f"Invalid age for account {account_number}.") from None
        if not 18 <= age <= 110:
            raise ImportValidationError(f"Invalid age for account {account_number}.")
        if fingerprint in customer_by_fingerprint:
            customer_data = customer_by_fingerprint[fingerprint]
            for field, value in (("Name", row["Name"]), ("Last_Name", row["Last_Name"]),
                                 ("Phone", row["Phone"]), ("Age", age),
                                 ("Country", row["Country"]), ("State", row["State"])):
                existing = customer_data[field]
                if str(existing).casefold() != str(value).strip().casefold():
                    raise ImportValidationError(f"Customer data differs across accounts for identity ending {identity_number[-4:]}.")
        else:
            customer_data = {
                "Name": row["Name"].strip(),
                "Last_Name": row["Last_Name"].strip(),
                "Phone": row["Phone"].strip(),
                "Age": age,
                "Country": row["Country"].strip(),
                "State": row["State"].strip(),
            }
            customer_by_fingerprint[fingerprint] = customer_data
        if not all(customer_data[field] for field in ("Name", "Last_Name", "Phone", "Country", "State")):
            raise ImportValidationError(f"Customer data is incomplete for account {account_number}.")
        if not re.fullmatch(r"\+?[0-9]{8,15}", customer_data["Phone"]):
            raise ImportValidationError(f"Invalid phone number for account {account_number}.")
        balance_minor = _minor_units(row["Balance"], f"Balance for {account_number}")
        if statuses[status] == "CLOSED" and balance_minor != 0:
            raise ImportValidationError(f"Closed account {account_number} must have a zero balance.")
        accounts[account_number] = {
            "row": row,
            "ifsc": re.sub(r"\s+", "", row["Ifsc_number"]).upper(),
            "status": statuses[status],
            "balance_minor": balance_minor,
            "fingerprint": fingerprint,
            "customer_data": customer_data,
        }

    transaction_rows = {}
    for history_file in sorted(Path(history_dir).glob("*.csv")):
        for row_number, row in enumerate(_read_csv(history_file), start=2):
            transaction_id = (row.get("Transaction_Id") or "").strip()
            account_number = (row.get("Account_No") or "").strip()
            if not transaction_id or account_number not in accounts:
                raise ImportValidationError(f"Invalid transaction reference in {history_file.name}, row {row_number}.")
            kind = _transaction_kind(row.get("Transaction_Type") or "")
            credit = _minor_units(row.get("CR") or "0", f"Credit in {history_file.name}, row {row_number}")
            debit = _minor_units(row.get("DR") or "0", f"Debit in {history_file.name}, row {row_number}")
            if bool(credit) == bool(debit):
                raise ImportValidationError(f"Exactly one of CR or DR must be positive in {history_file.name}, row {row_number}.")
            if (kind in {"OPENING_DEPOSIT", "DEPOSIT"} and not credit) or (
                kind == "WITHDRAWAL" and not debit
            ):
                raise ImportValidationError(f"Credit/debit direction does not match {kind} in {history_file.name}, row {row_number}.")
            try:
                created_at = datetime.fromisoformat(
                    f"{row['Date'].strip()}T{row['Time'].strip()}"
                ).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            except (KeyError, ValueError):
                raise ImportValidationError(f"Invalid transaction timestamp in {history_file.name}, row {row_number}.") from None
            previous = transaction_rows.get(transaction_id)
            if previous and (previous["kind"] != kind or previous["created_at"] != created_at):
                raise ImportValidationError(f"Transaction ID {transaction_id} has conflicting type or timestamp.")
            if previous is None:
                previous = transaction_rows[transaction_id] = {
                    "kind": kind,
                    "created_at": created_at,
                    "postings": {},
                }
            if account_number in previous["postings"]:
                raise ImportValidationError(f"Transaction {transaction_id} repeats account {account_number}.")
            previous["postings"][account_number] = debit - credit

    for legacy_id, transaction in transaction_rows.items():
        postings = transaction["postings"]
        if transaction["kind"] == "TRANSFER":
            if len(postings) != 2 or sum(postings.values()) != 0:
                raise ImportValidationError(
                    f"Transfer {legacy_id} must contain two matching account postings."
                )
        elif len(postings) != 1:
            raise ImportValidationError(
                f"Non-transfer transaction {legacy_id} must contain exactly one account posting."
            )

    calculated_balances = {number: 0 for number in accounts}
    for transaction in sorted(transaction_rows.values(), key=lambda item: item["created_at"]):
        for account_number, posting in transaction["postings"].items():
            calculated_balances[account_number] -= posting
    for account_number, account in accounts.items():
        if calculated_balances[account_number] != account["balance_minor"]:
            raise ImportValidationError(
                f"Balance mismatch for {account_number}: history gives {calculated_balances[account_number]} minor units, "
                f"account CSV gives {account['balance_minor']}. Import is stopped; reconcile the source files first."
            )
    return accounts, customer_by_fingerprint, transaction_rows


def import_legacy_csv(session: Session, actor_id, settings: Settings, accounts_path,
                      history_dir, dry_run=True):
    accounts, customers, transactions = _read_source(
        accounts_path, history_dir, settings.pii_hmac_key
    )
    actor = session.get(StaffUser, actor_id)
    if actor is None or actor.role != "ADMIN" or not actor.active:
        raise ImportValidationError("CSV import requires an active administrator actor.")
    if session.scalar(select(func.count()).select_from(Account)) or session.scalar(
        select(func.count()).select_from(Customer)
    ) or session.scalar(select(func.count()).select_from(LedgerTransaction)):
        raise ImportValidationError("CSV import only runs against an empty banking database.")
    branch_ifscs = set(session.scalars(select(Branch.ifsc)).all())
    if not branch_ifscs:
        raise ImportValidationError("No branch is configured; apply database migrations first.")
    for account_number, account in accounts.items():
        if account["ifsc"] not in branch_ifscs:
            raise ImportValidationError(f"Account {account_number} uses unknown IFSC {account['ifsc']}.")

    savepoint = session.begin_nested()
    try:
        clearing = session.scalar(
            select(LedgerAccount).where(LedgerAccount.code == CLEARING_ACCOUNT_CODE)
        )
        if clearing is None:
            clearing = LedgerAccount(
                code=CLEARING_ACCOUNT_CODE,
                account_type="CASH_CLEARING",
                account_id=None,
            )
            session.add(clearing)
            session.flush()

        customer_objects = {}
        for fingerprint, data in customers.items():
            customer = Customer(
                first_name=data["Name"],
                last_name=data["Last_Name"],
                phone=data["Phone"],
                age=data["Age"],
                country=data["Country"],
                state=data["State"],
                identity_fingerprint=fingerprint,
            )
            session.add(customer)
            customer_objects[fingerprint] = customer
        session.flush()

        branch_sequences = {
            branch.ifsc: branch.next_sequence
            for branch in session.scalars(select(Branch)).all()
        }
        account_objects = {}
        ledger_objects = {}
        for account_number, data in accounts.items():
            sequence = branch_sequences[data["ifsc"]]
            branch_sequences[data["ifsc"]] += 1
            account = Account(
                customer_id=customer_objects[data["fingerprint"]].id,
                account_number=account_number,
                ifsc=data["ifsc"],
                branch_sequence=sequence,
                status=data["status"],
                balance_minor=data["balance_minor"],
            )
            session.add(account)
            account_objects[account_number] = account
        session.flush()
        for account_number, account in account_objects.items():
            ledger = LedgerAccount(
                code=f"CUSTOMER:{account.id}",
                account_type="CUSTOMER_DEPOSIT",
                account_id=account.id,
            )
            session.add(ledger)
            ledger_objects[account_number] = ledger
        session.flush()
        for ifsc, next_sequence in branch_sequences.items():
            branch = session.get(Branch, ifsc)
            branch.next_sequence = next_sequence

        entry_count = 0
        for legacy_id, data in transactions.items():
            transaction_uuid = uuid.uuid5(NAMESPACE, legacy_id)
            request_hash = hashlib.sha256(
                json.dumps(
                    {"legacy_id": legacy_id, "kind": data["kind"], "postings": data["postings"]},
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            transaction = LedgerTransaction(
                id=transaction_uuid,
                actor_id=actor.id,
                idempotency_key="legacy-import:" + hashlib.sha256(legacy_id.encode("utf-8")).hexdigest(),
                request_hash=request_hash,
                kind=data["kind"],
                status="POSTED",
                memo=f"Imported legacy transaction {legacy_id}"[:250],
                result_id=legacy_id[:200],
                created_at=data["created_at"],
            )
            session.add(transaction)
            total = 0
            for account_number, amount in data["postings"].items():
                if amount:
                    session.add(LedgerEntry(
                        transaction_id=transaction_uuid,
                        ledger_account_id=ledger_objects[account_number].id,
                        amount_minor=amount,
                    ))
                    entry_count += 1
                    total += amount
            if total:
                session.add(LedgerEntry(
                    transaction_id=transaction_uuid,
                    ledger_account_id=clearing.id,
                    amount_minor=-total,
                ))
                entry_count += 1
        session.flush()
        if dry_run:
            savepoint.rollback()
        else:
            savepoint.commit()
        return ImportReport(
            accounts=len(accounts),
            customers=len(customers),
            transactions=len(transactions),
            ledger_entries=entry_count,
            dry_run=dry_run,
        )
    except Exception:
        if savepoint.is_active:
            savepoint.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description="Validate/import legacy banking CSV data.")
    parser.add_argument("--accounts", default="Accounts.csv")
    parser.add_argument("--history", default="Transaction_history")
    parser.add_argument("--apply", action="store_true", help="Commit after validation; default is dry-run.")
    args = parser.parse_args()
    settings = Settings.from_environment()
    engine = configure_database(settings)
    with Session(engine) as session:
        actor = session.scalar(select(StaffUser).where(StaffUser.role == "ADMIN", StaffUser.active.is_(True)))
        if actor is None:
            raise SystemExit("Create an active administrator before importing.")
        try:
            report = import_legacy_csv(
                session, actor.id, settings, args.accounts, args.history, dry_run=not args.apply
            )
            if args.apply:
                session.commit()
        except ImportValidationError as error:
            session.rollback()
            raise SystemExit(str(error)) from None
    mode = "committed" if args.apply else "dry-run only"
    print(
        f"{mode}: {report.accounts} accounts, {report.customers} customers, "
        f"{report.transactions} transactions, {report.ledger_entries} ledger entries"
    )


if __name__ == "__main__":
    main()