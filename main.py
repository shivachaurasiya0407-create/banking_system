import csv
from bank_system import Bank
from bank_core import Core
import datetime

FIELDNAMES = [
    "ID", "Employee_type", "Name", "Last_Name", "Phone", "Username", "Password", "First_Login",
    "Password_Changed", "Login_success", "Login_Time", "login_attempts","logout","logout_time"
]
logout = "No"

bank_obj = Bank()
core = Core()
def employee_main():
    
    menu = """------ Our Services ------
    1.Account Open
    2.Check Balance
    3.Deposite Money
    4.Withdraw Money
    5.Account info
    6.Transaction History
    7.Money Transfer
    8.Logout """

    services = {
        "1": bank_obj.create_account,
        "account open": bank_obj.create_account,
        "2": core.balance_check,
        "check balance": core.balance_check,
        "3": core.deposite_money,
        "deposite money": core.deposite_money,
        "4": core.withdraw_money,
        "withdraw money": core.withdraw_money,
        "5": core.account_info,
        "account info": core.account_info,
        "6": core.transaction_history,
        "transaction history": core.transaction_history,
        "7": core.money_transfer,
        "fund transfer": core.money_transfer,
    }

    while True:
        print("=" * 60)
        print(f"{'BANKING SYSTEM':^60}")
        print("=" * 60)
        print(menu)
        service = input("Enter Service : ").strip().lower()

        if service in ("8", "exit"):
            with open("employee.csv", "r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                employees = list(reader)
            for row in employees:
                if row.get("Login_success", "").upper() == "YES":
                    row["Login_success"] = "NO"
                    row["logout_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break
            row["logout"] = "Yes"
            with open("employee.csv", "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(employees)
            
            print(" ======= Logout Successful =======")

            break

        action = services.get(service)
        if action:
            action()
        else:
            print("Invalid Service! Please enter a valid option.\n")

def admin_main():

    menu = """------ Our Services ------
    1.Account Open
    2.Check Balance
    3.Deposite Money
    4.Withdraw Money
    5.Account info
    6.Transaction History
    7.Money Transfer
    8.Add Employee
    9.Remove Employee/View Employee
    10.Change Password
    11.Frezz Account or Employee
    12.Logout """

    services = {
        "1": bank_obj.create_account,
        "account open": bank_obj.create_account,
        "2": core.balance_check,
        "check balance": core.balance_check,
        "3": core.deposite_money,
        "deposite money": core.deposite_money,
        "4": core.withdraw_money,
        "withdraw money": core.withdraw_money,
        "5": core.account_info,
        "account info": core.account_info,
        "6": core.transaction_history,
        "transaction history": core.transaction_history,
        "7": core.money_transfer,
        "8": core.employee_add,
        "add employee": core.employee_add,
        # "9": core.remove_employee,
        # "remove employee": core.remove_employee,
        # "10": core.change_password,
        # "change password": core.change_password,
        "11": core.freeze_account,
        "freeze account": core.freeze_account,
        # "fund transfer": core.money_transfer,
    }

    while True:
        print("=" * 60)
        print(f"{'BANKING SYSTEM':^60}")
        print("=" * 60)
        print(menu)
        service = input("Enter Service : ").strip().lower()

        if service in ("12", "Logout"):
            with open("employee.csv", "r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                employees = list(reader)
            for row in employees:
                if row.get("Login_success", "").upper() == "YES":
                    row["Login_success"] = "NO"
                    row["logout_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break
            row["logout"] = "Yes"
            with open("employee.csv", "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(employees)
            
            print(" ======= Logout Successful =======")

            break

        action = services.get(service)
        if action:
            action()
        else:
            print("Invalid Service! Please enter a valid option.\n")
 

while True:
    login_result = core.login_employee()

    if login_result.status == "SUCCESS" and login_result.employee_type == "ADMIN":
        admin_main()
        # break
        continue
    elif login_result.status == "SUCCESS" and login_result.employee_type == "EMPLOYEE":
        employee_main()
        continue
    elif login_result.status == "CHANGED":
        continue
    else:
        choice = input("Do you want to try again? (y/n) : ").lower().strip()
        if choice != 'y':
            print("Exiting system...")
            break

# if __name__ == "__main__":
#     employee_main()