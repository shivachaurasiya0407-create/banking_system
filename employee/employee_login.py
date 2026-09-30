import csv
import hashlib
import os

file_path = "employee.csv"

def login_employee():
    print("-------- Login --------")
    while True:
        employee_username = input("Username : ").upper().strip()
        employee_password = input("Password : ").strip()
        hashed_password = hashlib.sha256(employee_password.encode()).hexdigest()

        all_employees = []
        user_found = False
        password_changed = False


        with open(file_path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("Username") == employee_username and row.get("Password") == hashed_password:
                    user_found = True
                    print("\nFirst Login / Password Change Required!")
                    new_password = input("Enter New Password : ").strip()
                    hashed_new_password = hashlib.sha256(new_password.encode()).hexdigest()
                    
                    row["Password"] = hashed_new_password
                    password_changed = True
                    print("Password updated successfully! Please login again with your new password.")

                all_employees.append(row)

        if password_changed:            
            fieldnames =["ID","Name","Phone","Username","Password"]
            with open(file_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(row)      
            return "CHANGED"

        if not user_found and os.path.exists(file_path):
            with open(file_path, "r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get("Username") == employee_username and row.get("Password") == hashed_password:
                        print("\nLogin Successful!")
                        return "SUCCESS"

        print("Invalid credentials. Try Again !")
        return "FAILED"
       