import string
import secrets
from employee.employee_csv import (
    hash_password,
    read_employees,
    write_employees,
)


def add_employee():

    print("-------- Add Employee --------")
    emp_type = input("Enter Employee Type (Admin/Employee) : ").strip().upper()
    if emp_type not in ["ADMIN", "EMPLOYEE"]:
        print("Invalid employee type. Please enter 'Admin' or 'Employee'.")
        return
    name = input("First Name : ").strip().upper()
    last_name = input("Last Name : ").strip().upper()
    if not _valid_name(name) or not _valid_name(last_name):
        print("Invalid name. Use letters, spaces, apostrophes, or hyphens.")
        return

    phone = input("Phone : ").strip()
    if len(phone) != 10 or not phone.isdigit():
        print("Invalid phone number. Please enter a 10-digit number.")
        return

    employees = read_employees()
    used_ids = {row.get("ID", "") for row in employees}
    used_usernames = {
        row.get("Username", "").strip().upper() for row in employees
    }
    while True:
        employee_id = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)
        username = name.replace(" ", "") + employee_id
        if employee_id not in used_ids and username.upper() not in used_usernames:
            break
    
    password_characters = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    available_characters = (
        string.ascii_letters + string.digits + string.punctuation
    )
    password_characters.extend(
        secrets.choice(available_characters) for _ in range(13)
    )
    secrets.SystemRandom().shuffle(password_characters)
    password = "".join(password_characters)
    print("Your username :",username)
    print("Your password :",password)

    employees.append({
        "ID": employee_id,
        "Employee_type": emp_type,
        "Name": name,
        "Last_Name": last_name,
        "Phone": phone,
        "Username": username,
        "Password": hash_password(password),
        "First_Login": "No",
        "Password_Changed": "NO",
        "Login_success": "NO",
        "Login_Time": "NOT_LOGGED_IN",
        "login_attempts": 0,
        "logout": "NO",
        "logout_time": "NOT_LOGGED_OUT",
        "Locked_Until": "",
    })
    write_employees(employees)


def _valid_name(value):
    return bool(value) and all(
        character.isalpha() or character in " -'" for character in value
    )

def employee_remove():
    print("-------- Remove Employee --------")
    emp_id = input("Enter Employee ID to remove: ").strip()
    if not emp_id.isdigit():
        print("Invalid ID. Please enter a valid numeric ID.")
        return

    emp_id = int(emp_id)
    employees = read_employees()
    updated_rows = [
        row for row in employees
        if not row.get("ID", "").isdigit() or int(row["ID"]) != emp_id
    ]
    employee_found = len(updated_rows) != len(employees)

    if not employee_found:
        print(f"No employee found with ID {emp_id}.")
        return
    removed_employees = [
        row for row in employees if row.get("ID", "").isdigit()
        and int(row["ID"]) == emp_id
    ]
    if any(row.get("Employee_type", "").upper() == "ADMIN" for row in removed_employees):
        remaining_admins = [
            row for row in updated_rows
            if row.get("Employee_type", "").strip().upper() == "ADMIN"
        ]
        if not remaining_admins:
            print("Cannot remove the last administrator.")
            return

    write_employees(updated_rows)

    print(f"Employee with ID {emp_id} has been removed successfully.")


def view_employees():
    employees = read_employees()
    if not employees:
        print("No employees are configured.")
        return
    print(f"{'ID':<8} {'TYPE':<12} {'NAME':<28} {'USERNAME':<24} {'PHONE'}")
    print("-" * 88)
    for row in employees:
        phone = row.get("Phone", "")
        masked_phone = f"{'*' * max(0, len(phone) - 4)}{phone[-4:]}" if phone else ""
        full_name = f"{row.get('Name', '')} {row.get('Last_Name', '')}".strip()
        print(
            f"{row.get('ID', ''):<8} {row.get('Employee_type', ''):<12} "
            f"{full_name[:27]:<28} {row.get('Username', ''):<24} {masked_phone}"
        )


def change_employee_password():
    employee_id = input("Employee ID: ").strip()
    employees = read_employees()
    employee = next(
        (row for row in employees if row.get("ID") == employee_id), None
    )
    if employee is None:
        print("Employee not found.")
        return

    password = input("New password: ").strip()
    if not _valid_password(password):
        print("Password must be 12+ characters with upper, lower, and numeric characters.")
        return
    employee["Password"] = hash_password(password)
    employee["Password_Changed"] = "NO"
    employee["First_Login"] = "No"
    employee["Login_success"] = "NO"
    employee["login_attempts"] = "0"
    employee["Locked_Until"] = ""
    write_employees(employees)
    print("Password reset. Employee must change it at next login.")


def _valid_password(password):
    return (
        len(password) >= 12
        and any(character.isupper() for character in password)
        and any(character.islower() for character in password)
        and any(character.isdigit() for character in password)
    )