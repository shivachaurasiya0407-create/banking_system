import csv
import hashlib
import datetime
from dataclasses import dataclass

file_path = "employee.csv"
FIELDNAMES = [
    "ID", "Employee_type","Name","Last_Name", "Phone", "Username", "Password", "First_Login",
    "Password_Changed", "Login_success", "Login_Time", "login_attempts","logout","logout_time"]

@dataclass
class LoginResult:
    status: str
    employee_type: str


def check_password(password):
    if len(password) < 8:
        return False
    if not any(char.isupper()for char in password):
        return False
    if not any(char.islower() for char in password):
        return  False
    if not any(char.isdigit() for char in password):
        return False
    
    if not any(char in r"!@#$%^&*()-_=+[{]}\|;:'\",<.>/?`~" for char in password):
        return False
    return True

def login_employee():
    print("-------- Login --------")
    while True:
        employee_type = input("Enter Employee Type (Admin/Employee) : ").strip().upper()
        if employee_type not in ["ADMIN", "EMPLOYEE"]:
            print("Invalid employee type. Please enter 'Admin' or 'Employee'.")
            continue
        employee_username = input("Username : ").upper().strip()
        employee_password = input("Password : ").strip()
        hashed_password = hashlib.sha256(employee_password.encode()).hexdigest()

        with open(file_path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            employees = list(reader)

        matched_row = next(
            (row for row in employees
             if row.get("Employee_type", "").upper() == employee_type
             and row.get("Username", "").upper() == employee_username
             and row.get("Password") == hashed_password),
            None,
        )

        if matched_row is None:
            
            print("Invalid credentials. Try Again ")
            continue

        if matched_row.get("Password_Changed", "").strip().upper() != "YES":
            print("\nFirst Login / Password Change Required!")
            new_password = input("Enter New Password : ").strip()
            if not check_password(new_password):
                print("Password does not meet the requirements  .")
                continue    

            matched_row["Password"] = hashlib.sha256(new_password.encode()).hexdigest()
            matched_row["First_Login"] = "Yes"
            matched_row["Password_Changed"] = "YES"
            matched_row["Login_success"] = "NO"
            matched_row["Login_Time"] = "NOT_LOGGED_IN"
            matched_row["login_attempts"] = "0"
            print("Password updated successfully! Please login again with your new password.")
            status = "CHANGED"
        else:
            print("\nLogin Successful!")
            matched_row["Login_success"] = "YES"
            matched_row["Login_Time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            matched_row["login_attempts"] = "0"
            status = "SUCCESS"

        employees = [
            {fieldname: row.get(fieldname, "") for fieldname in FIELDNAMES}
            for row in employees
        ]
        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(employees)
        return LoginResult(status=status, employee_type=employee_type)
       