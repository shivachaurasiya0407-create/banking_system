import csv
import hashlib
import datetime

file_path = "employee.csv"
FIELDNAMES = [
    "ID", "Name", "Phone", "Username", "Password", "First_Login",
    "Password_Changed", "Login_success", "Login_Time", "login_attempts",
]

def login_employee():
    print("-------- Login --------")
    while True:
        employee_username = input("Username : ").upper().strip()
        employee_password = input("Password : ").strip()
        hashed_password = hashlib.sha256(employee_password.encode()).hexdigest()

        with open(file_path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            employees = list(reader)

        matched_row = next(
            (row for row in employees
             if row.get("Username", "").upper() == employee_username
             and row.get("Password") == hashed_password),
            None,
        )

        if matched_row is None:
            
            print("Invalid credentials. Try Again !")
            continue

        if matched_row.get("Password_Changed", "").strip().upper() != "YES":
            print("\nFirst Login / Password Change Required!")
            new_password = input("Enter New Password : ").strip()
            if not new_password:
                print("Password cannot be empty.")
                continue

            matched_row["Password"] = hashlib.sha256(new_password.encode()).hexdigest()
            matched_row["First_Login"] = "Yes"
            matched_row["Password_Changed"] = "YES"
            matched_row["Login_success"] = "NO"
            matched_row["Login_Time"] = "NOT_LOGGED_IN"
            matched_row["login_attempts"] = "0"
            print("Password updated successfully! Please login again with your new password.")
            result = "CHANGED"
        else:
            print("\nLogin Successful!")
            matched_row["Login_success"] = "YES"
            matched_row["Login_Time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            matched_row["login_attempts"] = "0"
            result = "SUCCESS"

        employees = [
            {fieldname: row.get(fieldname, "") for fieldname in FIELDNAMES}
            for row in employees
        ]
        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(employees)
        return result
       