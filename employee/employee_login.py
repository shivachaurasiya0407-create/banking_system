import datetime
import secrets
from dataclasses import dataclass

from employee.employee_csv import (
    hash_password,
    read_employees,
    verify_password,
    write_employees,
)


MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@dataclass
class LoginResult:
    status: str
    employee_type: str
    employee_id: str = ""


def check_password(password):
    return (
        len(password) >= 12
        and any(char.isupper() for char in password)
        and any(char.islower() for char in password)
        and any(char.isdigit() for char in password)
    )


def _valid_person_name(value):
    return bool(value) and all(
        character.isalpha() or character in " -'" for character in value
    )


def _initialize_first_admin():
    print("No employees configured. Set up the initial administrator.")
    name = input("Administrator first name: ").strip().upper()
    last_name = input("Administrator last name: ").strip().upper()
    username = input("Administrator username: ").strip().upper()
    password = input("Administrator password (12+ chars, upper/lower/digit): ")
    confirmation = input("Confirm password: ")
    if (
        not _valid_person_name(name)
        or not _valid_person_name(last_name)
        or not username
    ):
        print("Valid names and a username are required; setup was not saved.")
        return
    if password != confirmation or not check_password(password):
        print("Passwords did not match or did not meet the requirements.")
        return

    employee_id = str(secrets.randbelow(9_000_000) + 1_000_000)
    write_employees(
        [
            {
                "ID": employee_id,
                "Employee_type": "ADMIN",
                "Name": name,
                "Last_Name": last_name,
                "Phone": "",
                "Username": username,
                "Password": hash_password(password),
                "First_Login": "Yes",
                "Password_Changed": "YES",
                "Login_success": "NO",
                "Login_Time": "NOT_LOGGED_IN",
                "login_attempts": "0",
                "logout": "NO",
                "logout_time": "NOT_LOGGED_OUT",
                "Locked_Until": "",
            }
        ]
    )
    print("Initial administrator created. Please log in.")


def _lockout_active(employee, now):
    locked_until = employee.get("Locked_Until", "").strip()
    if not locked_until:
        return False
    try:
        return datetime.datetime.fromisoformat(locked_until) > now
    except ValueError:
        employee["Locked_Until"] = ""
        return False


def login_employee():
    employees = read_employees()
    if not employees:
        _initialize_first_admin()
        return LoginResult(status="CHANGED", employee_type="")

    print("-------- Login --------")
    for _ in range(MAX_LOGIN_ATTEMPTS):
        employee_type = input("Enter Employee Type (Admin/Employee): ").strip().upper()
        if employee_type not in {"ADMIN", "EMPLOYEE"}:
            print("Invalid employee type. Enter Admin or Employee.")
            continue
        username = input("Username: ").strip().upper()
        password = input("Password: ")
        employee = next(
            (
                row for row in employees
                if row.get("Username", "").strip().upper() == username
            ),
            None,
        )
        now = datetime.datetime.now()
        if employee is None:
            print("Invalid credentials.")
            continue
        if _lockout_active(employee, now):
            print("Account temporarily locked. Try again later.")
            continue
        if employee.get("Employee_type", "").strip().upper() != employee_type:
            verified, needs_upgrade = False, False
        else:
            verified, needs_upgrade = verify_password(
                password, employee.get("Password", "")
            )

        if not verified:
            try:
                attempts = int(employee.get("login_attempts", "0") or 0) + 1
            except ValueError:
                attempts = 1
            employee["login_attempts"] = str(attempts)
            if attempts >= MAX_LOGIN_ATTEMPTS:
                employee["Locked_Until"] = (
                    now + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                ).isoformat(timespec="seconds")
                employee["login_attempts"] = "0"
                print(f"Too many failed attempts. Locked for {LOCKOUT_MINUTES} minutes.")
            else:
                print("Invalid credentials.")
            write_employees(employees)
            continue

        if employee.get("Password_Changed", "").strip().upper() != "YES":
            new_password = input("Set a new password (12+ chars, upper/lower/digit): ")
            confirmation = input("Confirm new password: ")
            if new_password != confirmation or not check_password(new_password):
                print("Passwords did not match or did not meet the requirements.")
                continue
            employee["Password"] = hash_password(new_password)
            employee["First_Login"] = "Yes"
            employee["Password_Changed"] = "YES"
            employee["login_attempts"] = "0"
            employee["Locked_Until"] = ""
            write_employees(employees)
            print("Password updated. Please log in again.")
            return LoginResult(status="CHANGED", employee_type=employee_type)

        if needs_upgrade:
            employee["Password"] = hash_password(password)
        employee["Login_success"] = "YES"
        employee["Login_Time"] = now.strftime("%Y-%m-%d %H:%M:%S")
        employee["login_attempts"] = "0"
        employee["Locked_Until"] = ""
        write_employees(employees)
        print("Login successful.")
        return LoginResult(
            status="SUCCESS",
            employee_type=employee_type,
            employee_id=employee.get("ID", ""),
        )

    return LoginResult(status="FAILED", employee_type="")
