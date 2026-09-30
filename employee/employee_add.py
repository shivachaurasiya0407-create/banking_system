import csv
import os
import string
import secrets
import hashlib
# FILE = "employee.csv"
file_path ="employee.csv"
def add_employee():

    print("-------- Add Employee --------")
    name = str(input("Name : ")).upper()
    for i in name:
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
    fieldnames = ["ID","Name","Phone","Username","Password"]
    with open (file_path,"a",newline="",encoding="utf-8") as file :
       writer = csv.DictWriter(file,fieldnames=fieldnames)
       if not file_exists or os.path.getsize("employee.csv") == 0:
           writer.writeheader()
       writer.writerow({
           "ID" : id,
           "Name" : name,
           "Phone" : phone,
           "Username" : username,
           "Password" : password
        })    
x = input("Do you want to add employee (y/n) : ").lower()
if "y":
   add = add_employee()

