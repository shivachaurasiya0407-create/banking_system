import csv
import hashlib
import hmac
import os
import secrets
import tempfile
from pathlib import Path


FILE_PATH = str(Path(__file__).resolve().parent.parent / "employee.csv")
PBKDF2_ITERATIONS = 600_000
FIELDNAMES = [
    "ID",
    "Employee_type",
    "Name",
    "Last_Name",
    "Phone",
    "Username",
    "Password",
    "First_Login",
    "Password_Changed",
    "Login_success",
    "Login_Time",
    "login_attempts",
    "logout",
    "logout_time",
    "Locked_Until",
]


def _normalize_employee(row):
    employee = dict(row)
    legacy_last_name = employee.pop("Last_name", None)
    if not employee.get("Last_Name"):
        employee["Last_Name"] = legacy_last_name or ""
    employee.setdefault("Locked_Until", "")
    return employee


def read_employees(file_path=FILE_PATH):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        return [_normalize_employee(row) for row in csv.DictReader(file)]


def write_employees(employees, file_path=FILE_PATH):
    rows = [_normalize_employee(row) for row in employees]
    extra_fieldnames = []
    for row in rows:
        for fieldname in row:
            if fieldname not in FIELDNAMES and fieldname not in extra_fieldnames:
                extra_fieldnames.append(fieldname)

    directory = os.path.dirname(os.path.abspath(file_path))
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", dir=directory, delete=False
        ) as file:
            temporary_path = file.name
            writer = csv.DictWriter(
                file, fieldnames=FIELDNAMES + extra_fieldnames
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, file_path)
    except Exception:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored_password):
    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            algorithm, iterations, salt_hex, digest_hex = stored_password.split("$")
            if algorithm != "pbkdf2_sha256":
                return False, False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(digest.hex(), digest_hex), False
        except (ValueError, TypeError):
            return False, False

    legacy_digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(legacy_digest, stored_password):
        return True, True
    return False, False
