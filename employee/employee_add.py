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
        print("Invalid name. Please enter a valid name.")
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
    FIELDNAMES = ["ID","Employee_type", "Name","Last_Name", "Phone", "Username", "Password", "First_Login","Password_Changed", "Login_success", "Login_Time", "login_attempts","logout","logout_time"]

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
# x = add_employee()
# print(x)       