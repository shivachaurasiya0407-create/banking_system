import csv
import datetime
import importlib
import hashlib
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from bank_system import Bank
from employee.employee_csv import hash_password, read_employees, verify_password, write_employees
from employee import employee_login


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


class BankingOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.accounts_path = self.root / "Accounts.csv"
        self.history_path = self.root / "Transaction_history"
        self.bank = Bank(self.accounts_path, self.history_path)
        self.accounts = [
            {
                "Name": "ALICE",
                "Last_Name": "SMITH",
                "Phone": "0123456789",
                "Age": "30",
                "Gender": "Other",
                "Country": "India",
                "State": "Delhi",
                "Aadhar": "123456789012",
                "Account_no": "1234567890",
                "Ifsc_number": "SHIV0000001",
                "Balance": "5000.00",
                "Status": "Active",
            },
            {
                "Name": "BOB",
                "Last_Name": "JONES",
                "Phone": "9876543210",
                "Age": "31",
                "Gender": "Other",
                "Country": "India",
                "State": "Goa",
                "Aadhar": "987654321012",
                "Account_no": "9876543210",
                "Ifsc_number": "SHIV0000001",
                "Balance": "1000.00",
                "Status": "Active",
            },
        ]
        with self.accounts_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=ACCOUNT_FIELDS)
            writer.writeheader()
            writer.writerows(self.accounts)

    def tearDown(self):
        self.temp_directory.cleanup()

    def account_balance(self, account_no):
        return self.bank.find_account(account_no, "SHIV0000001")["Balance"]

    def test_deposit_accepts_cents_and_writes_history(self):
        balance = self.bank.deposit("1234567890", "SHIV0000001", "25.50")
        self.assertEqual(balance, Decimal("5025.50"))
        self.assertEqual(self.account_balance("1234567890"), "5025.50")
        with (self.history_path / "1234567890.csv").open(
            newline="", encoding="utf-8"
        ) as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(rows[-1]["CR"], "25.50")
        self.assertEqual(rows[-1]["DR"], "0.00")

    def test_withdrawal_rejects_insufficient_funds_without_mutation(self):
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.bank.withdraw("9876543210", "SHIV0000001", "1000.01")
        self.assertEqual(self.account_balance("9876543210"), "1000.00")
        self.assertFalse((self.history_path / "9876543210.csv").exists())

    def test_transfer_updates_both_balances_and_both_histories(self):
        sender_balance, receiver_balance = self.bank.transfer(
            "1234567890", "SHIV0000001", "9876543210", "SHIV0000001", "250.75"
        )
        self.assertEqual((sender_balance, receiver_balance), (4749.25, 1250.75))
        self.assertEqual(self.account_balance("1234567890"), "4749.25")
        self.assertEqual(self.account_balance("9876543210"), "1250.75")
        for account_no, expected_type, counterparty in (
            ("1234567890", "Transfer Out", "9876543210"),
            ("9876543210", "Transfer In", "1234567890"),
        ):
            with (self.history_path / f"{account_no}.csv").open(
                newline="", encoding="utf-8"
            ) as file:
                row = list(csv.DictReader(file))[-1]
            self.assertEqual(row["Transaction_Type"], expected_type)
            self.assertEqual(row["Counterparty_Account"], counterparty)

    def test_invalid_and_self_transfer_do_not_mutate_balances(self):
        with self.assertRaisesRegex(ValueError, "Receiver"):
            self.bank.transfer(
                "1234567890", "SHIV0000001", "0000000000", "SHIV0000001", 10
            )
        with self.assertRaisesRegex(ValueError, "different"):
            self.bank.transfer(
                "1234567890", "SHIV0000001", "1234567890", "SHIV0000001", 10
            )
        with self.assertRaisesRegex(ValueError, "two decimal"):
            self.bank.deposit("1234567890", "SHIV0000001", "1.001")
        self.assertEqual(self.account_balance("1234567890"), "5000.00")
        self.assertEqual(self.account_balance("9876543210"), "1000.00")

    def test_status_changes_append_history_without_dropping_account_rows(self):
        self.bank.set_account_status("1234567890", "SHIV0000001", "Frozen")
        self.bank.set_account_status("1234567890", "SHIV0000001", "Active")
        self.assertEqual(len(self.bank._read_accounts()), 2)
        self.assertEqual(self.account_balance("1234567890"), "5000.00")
        with (self.root / "freeze.csv").open(newline="", encoding="utf-8") as file:
            events = list(csv.DictReader(file))
        self.assertEqual([event["Status"] for event in events], ["Frozen", "Active"])

    def test_legacy_transaction_file_is_preserved_when_upgraded(self):
        self.history_path.mkdir()
        legacy_path = self.history_path / "1234567890.csv"
        with legacy_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "Transaction_Id",
                    "Account_No",
                    "Date",
                    "Time",
                    "Transaction_Type",
                    "CR",
                    "DR",
                    "Balance",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Transaction_Id": "TXNOLD",
                    "Account_No": "1234567890",
                    "Date": "2025-01-01",
                    "Time": "10:00:00",
                    "Transaction_Type": "Deposit",
                    "CR": "10",
                    "DR": "0",
                    "Balance": "5010",
                }
            )
        self.bank.deposit("1234567890", "SHIV0000001", "10")
        with legacy_path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Transaction_Id"], "TXNOLD")
        self.assertEqual(rows[0]["Ifsc_Number"], "SHIV0000001")

    def test_account_opening_normalizes_static_choices_and_preserves_phone(self):
        answers = [
            "maria",
            "o'neal",
            "0123456789",
            "1",
            "29",
            "india",
            "delhi",
            "111122223333",
            "2000.50",
        ]
        with patch("builtins.input", side_effect=answers):
            self.bank.create_account()
        accounts = self.bank._read_accounts()
        created = accounts[-1]
        self.assertEqual(created["Name"], "MARIA")
        self.assertEqual(created["Last_Name"], "O'NEAL")
        self.assertEqual(created["Phone"], "0123456789")
        self.assertEqual(created["Country"], "India")
        self.assertEqual(created["State"], "Delhi")
        self.assertEqual(created["Balance"], "2000.50")
        self.assertEqual(len(created["Account_no"]), 10)


class EmployeeDataTests(unittest.TestCase):
    def test_employee_csv_normalizes_old_last_name_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "employee.csv"
            path.write_text(
                "ID,Employee_type,Name,Last_name,Username,Password\n"
                "1,ADMIN,ALICE,SMITH,ALICE1,legacyhash\n",
                encoding="utf-8",
            )
            self.assertEqual(read_employees(path)[0]["Last_Name"], "SMITH")
            write_employees(read_employees(path), path)
            with path.open(newline="", encoding="utf-8") as file:
                self.assertIn("Last_Name", csv.DictReader(file).fieldnames)

    def test_password_hash_is_salted_and_verifiable(self):
        first = hash_password("SafePassword123")
        second = hash_password("SafePassword123")
        self.assertNotEqual(first, second)
        self.assertEqual(verify_password("SafePassword123", first), (True, False))
        self.assertEqual(verify_password("wrong", first), (False, False))

    def test_main_is_import_safe(self):
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            importlib.import_module("main")

    def test_importing_employee_add_does_not_prompt_or_add_employee(self):
        with patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            module = importlib.import_module("employee.employee_add")
            importlib.reload(module)

    def test_legacy_sha256_password_is_upgraded_after_login(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "employee.csv"
            old_hash = hashlib.sha256(b"LegacyPass123").hexdigest()
            write_employees(
                [
                    {
                        "ID": "12",
                        "Employee_type": "EMPLOYEE",
                        "Name": "ALICE",
                        "Last_Name": "SMITH",
                        "Username": "ALICE12",
                        "Password": old_hash,
                        "Password_Changed": "YES",
                        "login_attempts": "0",
                    }
                ],
                path,
            )
            with (
                patch.object(employee_login, "read_employees", lambda: read_employees(path)),
                patch.object(
                    employee_login,
                    "write_employees",
                    lambda employees: write_employees(employees, path),
                ),
                patch(
                    "builtins.input",
                    side_effect=["EMPLOYEE", "ALICE12", "LegacyPass123"],
                ),
            ):
                result = employee_login.login_employee()
            self.assertEqual(result.status, "SUCCESS")
            migrated_hash = read_employees(path)[0]["Password"]
            self.assertTrue(migrated_hash.startswith("pbkdf2_sha256$"))
            self.assertEqual(verify_password("LegacyPass123", migrated_hash), (True, False))

    def test_five_wrong_passwords_apply_temporary_lockout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "employee.csv"
            write_employees(
                [
                    {
                        "ID": "12",
                        "Employee_type": "EMPLOYEE",
                        "Name": "ALICE",
                        "Last_Name": "SMITH",
                        "Username": "ALICE12",
                        "Password": hash_password("CorrectPass123"),
                        "Password_Changed": "YES",
                        "login_attempts": "0",
                    }
                ],
                path,
            )
            answers = ["EMPLOYEE", "ALICE12", "WrongPass123"] * 5
            with (
                patch.object(employee_login, "read_employees", lambda: read_employees(path)),
                patch.object(
                    employee_login,
                    "write_employees",
                    lambda employees: write_employees(employees, path),
                ),
                patch("builtins.input", side_effect=answers),
            ):
                result = employee_login.login_employee()
            self.assertEqual(result.status, "FAILED")
            locked_until = datetime.datetime.fromisoformat(
                read_employees(path)[0]["Locked_Until"]
            )
            self.assertGreater(locked_until, datetime.datetime.now())

    def test_empty_employee_store_requires_explicit_admin_setup(self):
        saved_employees = []
        answers = [
            "ALEX",
            "ADMIN",
            "ROOT",
            "SecureAdmin123",
            "SecureAdmin123",
        ]
        with (
            patch.object(employee_login, "read_employees", return_value=[]),
            patch.object(
                employee_login,
                "write_employees",
                side_effect=lambda rows: saved_employees.extend(rows),
            ),
            patch("builtins.input", side_effect=answers),
        ):
            result = employee_login.login_employee()
        self.assertEqual(result.status, "CHANGED")
        self.assertEqual(len(saved_employees), 1)
        self.assertEqual(saved_employees[0]["Employee_type"], "ADMIN")
        self.assertTrue(
            verify_password("SecureAdmin123", saved_employees[0]["Password"])[0]
        )


if __name__ == "__main__":
    unittest.main()
