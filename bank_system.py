import csv
import os
import secrets
import tempfile
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


ACCOUNT_FIELDS = [
    "Name",
    "Last_Name",
    "Phone",
    "Age",
    "Gender",
    "Country",
    "State",
    "Aadhar",
    "Account_no",
    "Ifsc_number",
    "Balance",
    "Status",
]
TRANSACTION_FIELDS = [
    "Transaction_Id",
    "Account_No",
    "Ifsc_Number",
    "Date",
    "Time",
    "Transaction_Type",
    "CR",
    "DR",
    "Balance",
    "Counterparty_Account",
]
MIN_OPENING_BALANCE = Decimal("2000.00")
PROJECT_DIR = Path(__file__).resolve().parent
INDIA_STATES = (
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
)


def _atomic_write_csv(file_path, fieldnames, rows):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary_path = file.name
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise


def _money(value):
    try:
        amount = Decimal(str(value))
        cents_amount = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("Amount must be a valid number.") from None
    if not amount.is_finite():
        raise ValueError("Amount must be a finite number.")
    if amount != cents_amount:
        raise ValueError("Amount cannot have more than two decimal places.")
    if cents_amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return cents_amount


class Bank:
    FILE = str(PROJECT_DIR / "Accounts.csv")
    HISTORY_DIR = str(PROJECT_DIR / "Transaction_history")
    BANK_CODE = "SHIV"
    BRANCH_CODE = "000001"

    def __init__(self, accounts_file=None, history_dir=None):
        self.accounts_file = Path(accounts_file or self.FILE)
        self.history_dir = Path(history_dir or self.HISTORY_DIR)
        self.FILE = str(self.accounts_file)
        self.balance = Decimal("0.00")
        self.branch_number = 1

    def _read_accounts(self):
        if not self.accounts_file.exists():
            return []
        with self.accounts_file.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                return []
            return list(reader)

    def _write_accounts(self, accounts):
        extra_fields = []
        for row in accounts:
            for field in row:
                if field not in ACCOUNT_FIELDS and field not in extra_fields:
                    extra_fields.append(field)
        _atomic_write_csv(self.accounts_file, ACCOUNT_FIELDS + extra_fields, accounts)

    def create_account(self):
        print("\n--- Account Opening ---")
        name = self._prompt_name("First name: ")
        if name is None:
            return
        last_name = self._prompt_name("Last name: ")
        if last_name is None:
            return

        while True:
            phone = input("Phone number (10 digits): ").strip()
            if len(phone) == 10 and phone.isdigit():
                break
            print("Enter a valid 10-digit phone number.")

        while True:
            gender_option = input(
                "Select Gender (1. Male, 2. Female, 3. Other): "
            ).strip().lower()
            gender = {"1": "Male", "2": "Female", "3": "Other"}.get(gender_option)
            if gender:
                break
            print("Choose 1, 2, or 3.")

        while True:
            try:
                age = int(input("Age (18-110): ").strip())
            except ValueError:
                print("Enter age as a whole number.")
                continue
            if 18 <= age <= 110:
                break
            print("Account holder must be between 18 and 110.")

        country = self._prompt_choice("Country (India): ", ("India",))
        state = self._prompt_choice("State: ", INDIA_STATES)
        while True:
            aadhar = input("Aadhaar (12 digits): ").strip()
            if len(aadhar) != 12 or not aadhar.isdigit():
                print("Enter a valid 12-digit Aadhaar number.")
            elif self.aadhar_exists(aadhar):
                print("An account with this Aadhaar number already exists.")
                return
            else:
                break

        while True:
            opening_balance = input(
                f"Opening deposit (minimum Rs. {MIN_OPENING_BALANCE:.2f}): "
            ).strip()
            try:
                amount = _money(opening_balance)
            except ValueError:
                print("Enter a valid positive amount.")
                continue
            if amount >= MIN_OPENING_BALANCE:
                break
            print(f"Minimum opening deposit is Rs. {MIN_OPENING_BALANCE:.2f}.")

        accounts = self._read_accounts()
        used_accounts = {row.get("Account_no", "") for row in accounts}
        while True:
            account_no = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)
            if account_no not in used_accounts:
                break
        ifsc = f"{self.BANK_CODE}0{self.BRANCH_CODE}"
        account = {
            "Name": name,
            "Last_Name": last_name,
            "Phone": phone,
            "Age": str(age),
            "Gender": gender,
            "Country": country,
            "State": state,
            "Aadhar": aadhar,
            "Account_no": account_no,
            "Ifsc_number": ifsc,
            "Balance": f"{amount:.2f}",
            "Status": "Active",
        }
        accounts.append(account)
        self._write_accounts(accounts)
        self.log_transaction(account_no, ifsc, "Opening Deposit", amount, 0, amount)
        print("Account created successfully.")
        print("Account number:", account_no)
        print("IFSC number:", ifsc)
        print("Opening balance: Rs.", f"{amount:.2f}")

    @staticmethod
    def _prompt_name(prompt):
        while True:
            value = input(prompt).strip()
            if value and all(
                char.isalpha() or char in " -'" for char in value
            ):
                return value.upper()
            print("Enter a name using letters, spaces, apostrophes, or hyphens.")

    @staticmethod
    def _prompt_choice(prompt, choices):
        choices_by_normalized_name = {choice.casefold(): choice for choice in choices}
        while True:
            value = input(prompt).strip()
            choice = choices_by_normalized_name.get(value.casefold())
            if choice:
                return choice
            print("Invalid selection. Please enter a supported value.")

    def aadhar_exists(self, aadhar_no):
        return any(row.get("Aadhar", "").strip() == str(aadhar_no).strip()
                   for row in self._read_accounts())

    def account_exists(self, account_no):
        return any(row.get("Account_no", "").strip() == str(account_no).strip()
                   for row in self._read_accounts())

    def ifsc_exists(self, ifsc_number):
        return any(row.get("Ifsc_number", "").strip() == str(ifsc_number).strip()
                   for row in self._read_accounts())

    def find_account(self, account_no, ifsc_number, status=None):
        for row in self._read_accounts():
            if (
                row.get("Account_no", "").strip() == str(account_no).strip()
                and row.get("Ifsc_number", "").strip().casefold()
                == str(ifsc_number).strip().casefold()
                and (status is None or row.get("Status", "").strip() == status)
            ):
                return row
        return None

    def log_transaction(
        self,
        account_no,
        ifsc_number,
        txn_type,
        cr,
        dr,
        balance,
        counterparty="",
    ):
        path = self.history_dir / f"{account_no}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        row = {
            "Transaction_Id": f"TXN{uuid.uuid4().hex[:12].upper()}",
            "Account_No": str(account_no),
            "Ifsc_Number": str(ifsc_number),
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%H:%M:%S"),
            "Transaction_Type": txn_type,
            "CR": f"{Decimal(str(cr)):.2f}",
            "DR": f"{Decimal(str(dr)):.2f}",
            "Balance": f"{Decimal(str(balance)):.2f}",
            "Counterparty_Account": str(counterparty),
        }
        transactions = []
        if path.exists() and path.stat().st_size > 0:
            with path.open("r", newline="", encoding="utf-8-sig") as file:
                for old_row in csv.DictReader(file):
                    transactions.append(
                        {
                            field: old_row.get(field, "")
                            or (
                                str(ifsc_number)
                                if field == "Ifsc_Number"
                                else "0.00"
                                if field in {"CR", "DR"}
                                else ""
                            )
                            for field in TRANSACTION_FIELDS
                        }
                    )
        transactions.append(row)
        _atomic_write_csv(path, TRANSACTION_FIELDS, transactions)

    def update_balance(self, account_no, new_balance):
        balance = Decimal(str(new_balance)).quantize(Decimal("0.01"))
        if not balance.is_finite() or balance < 0:
            raise ValueError("Balance must be a finite, non-negative amount.")
        accounts = self._read_accounts()
        updated = False
        for row in accounts:
            if row.get("Account_no", "").strip() == str(account_no).strip():
                row["Balance"] = f"{balance:.2f}"
                updated = True
        if not updated:
            raise ValueError("Account not found.")
        self._write_accounts(accounts)

    def deposit(self, account_no, ifsc_number, amount):
        amount = _money(amount)
        account = self.find_account(account_no, ifsc_number, status="Active")
        if account is None:
            raise ValueError("Account not found or not active.")
        new_balance = Decimal(account["Balance"]) + amount
        self.update_balance(account_no, new_balance)
        self.log_transaction(
            account_no, ifsc_number, "Deposit", amount, 0, new_balance
        )
        return new_balance

    def withdraw(self, account_no, ifsc_number, amount):
        amount = _money(amount)
        account = self.find_account(account_no, ifsc_number, status="Active")
        if account is None:
            raise ValueError("Account not found or not active.")
        current_balance = Decimal(account["Balance"])
        if amount > current_balance:
            raise ValueError("Insufficient balance.")
        new_balance = current_balance - amount
        self.update_balance(account_no, new_balance)
        self.log_transaction(
            account_no, ifsc_number, "Withdrawal", 0, amount, new_balance
        )
        return new_balance

    def transfer(
        self, sender_no, sender_ifsc, receiver_no, receiver_ifsc, amount
    ):
        amount = _money(amount)
        if (
            str(sender_no).strip() == str(receiver_no).strip()
            and str(sender_ifsc).strip().casefold()
            == str(receiver_ifsc).strip().casefold()
        ):
            raise ValueError("Sender and receiver must be different accounts.")
        accounts = self._read_accounts()
        sender = next(
            (
                row for row in accounts
                if row.get("Account_no", "").strip() == str(sender_no).strip()
                and row.get("Ifsc_number", "").strip().casefold()
                == str(sender_ifsc).strip().casefold()
                and row.get("Status", "").strip() == "Active"
            ),
            None,
        )
        receiver = next(
            (
                row for row in accounts
                if row.get("Account_no", "").strip() == str(receiver_no).strip()
                and row.get("Ifsc_number", "").strip().casefold()
                == str(receiver_ifsc).strip().casefold()
                and row.get("Status", "").strip() == "Active"
            ),
            None,
        )
        if sender is None:
            raise ValueError("Sender account not found or not active.")
        if receiver is None:
            raise ValueError("Receiver account not found or not active.")
        sender_balance = Decimal(sender["Balance"])
        if amount > sender_balance:
            raise ValueError("Insufficient balance.")
        new_sender_balance = sender_balance - amount
        new_receiver_balance = Decimal(receiver["Balance"]) + amount
        sender["Balance"] = f"{new_sender_balance:.2f}"
        receiver["Balance"] = f"{new_receiver_balance:.2f}"
        self._write_accounts(accounts)
        self.log_transaction(
            sender_no,
            sender_ifsc,
            "Transfer Out",
            0,
            amount,
            new_sender_balance,
            receiver_no,
        )
        self.log_transaction(
            receiver_no,
            receiver_ifsc,
            "Transfer In",
            amount,
            0,
            new_receiver_balance,
            sender_no,
        )
        return new_sender_balance, new_receiver_balance

    def set_account_status(self, account_no, ifsc_number, status):
        if status not in {"Active", "Frozen"}:
            raise ValueError("Unsupported account status.")
        accounts = self._read_accounts()
        account = next(
            (
                row for row in accounts
                if row.get("Account_no", "").strip() == str(account_no).strip()
                and row.get("Ifsc_number", "").strip().casefold()
                == str(ifsc_number).strip().casefold()
            ),
            None,
        )
        if account is None:
            raise ValueError("Account not found.")
        if account.get("Status", "").strip() == status:
            raise ValueError(f"Account is already {status.lower()}.")
        account["Status"] = status
        self._write_accounts(accounts)
        self._log_status_change(account_no, ifsc_number, status)

    def _log_status_change(self, account_no, ifsc_number, status):
        path = self.history_dir.parent / "freeze.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = path.exists() and path.stat().st_size > 0
        with path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["Account_No", "Ifsc_Number", "Date_Time", "Status"],
            )
            if not exists:
                writer.writeheader()
            writer.writerow(
                {
                    "Account_No": str(account_no),
                    "Ifsc_Number": str(ifsc_number),
                    "Date_Time": datetime.now().isoformat(timespec="seconds"),
                    "Status": status,
                }
            )
