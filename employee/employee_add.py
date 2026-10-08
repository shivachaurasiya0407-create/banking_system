import csv
import os
import string
import secrets
import hashlib
file_path ="employee.csv"
def add_employee():

    print("-------- Add Employee --------")
    emp_type = input("Enter Employee Type (Admin/Employee) : ").strip().upper()
    if emp_type not in ["ADMIN", "EMPLOYEE"]:
        print("Invalid employee type. Please enter 'Admin' or 'Employee'.")
        return
    name = str(input("Name : ")).upper()
    last_name = str(input("Last Name : ")).upper()
    for i in name and last_name:
      if not i.isalpha() and i != " ":
        print("Invalid name. Please Enter a valid name.")
        return
    phone = int(input("Phone : "))
    if not str(phone).isdigit() or len(str(phone)) != 10:
       print("Invalid phone number. Please enter a 10-digit number.")
       return

    id = secrets.randbelow(10000) + 1
    
    char =string.ascii_letters +string.digits + string.punctuation
    password = ''.join(secrets.choice(char) for _ in range(12) )
    username = name + str(id)
    print("Your username :",username)
    print("Your password :",password)

    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    password = hashed_password

    file_exists = os.path.exists("employee.csv")
    
    FIELDNAMES = [
    "ID", "Employee_type","Name","Last_Name", "Phone", "Username", "Password", "First_Login",
    "Password_Changed", "Login_success", "Login_Time", "login_attempts","logout","logout_time"]

    with open (file_path,"a",newline="",encoding="utf-8") as file :
       writer = csv.DictWriter(file,fieldnames=FIELDNAMES)
       if not file_exists or os.path.getsize("employee.csv") == 0:
           writer.writeheader()
       writer.writerow({
           "ID" : id,
           "Employee_type" : emp_type,
           "Name" : name,
           "Last_Name" : last_name,
           "Phone" : phone,
           "Username" : username,
           "Password" : password,
           "First_Login" : "No",
           "Password_Changed" : "NO",
           "Login_success" : "NO",
           "Login_Time" : "NOT_LOGGED_IN",
           "login_attempts" : 0,
           "logout" : "NO",
           "logout_time" : "NOT_LOGGED_OUT"
        })    


def employee_remove():
    print("-------- Remove Employee --------")
    emp_id = input("Enter Employee ID to remove: ").strip()
    if not emp_id.isdigit():
        print("Invalid ID. Please enter a valid numeric ID.")
        return

    emp_id = int(emp_id)
    file_path = "employee.csv"
    updated_rows = []
    employee_found = False

    with open(file_path, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if int(row["ID"]) == emp_id:
                employee_found = True
                continue  # Skip the row to be removed
            updated_rows.append(row)

    if not employee_found:
        print(f"No employee found with ID {emp_id}.")
        return

    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Employee with ID {emp_id} has been removed successfully.")