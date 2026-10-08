from bank_system import Bank
import csv
import os
import datetime
def freeze_account():
    file_path = "freeze.csv"
    bank = Bank()
    print(" ======= Freeze Account =======")
    account_no = input("Account Number to freeze: ")
    ifsc_number = input("IFSC code : ")
    if not account_no.isdigit() and len(account_no) == 10:
        print("Enter Account number in digit")
        return
    account = bank.find_account(account_no,ifsc_number)
    if account is None:
        print("Invalid Account and IFSC code")
        return
    print(f"Account {account_no} has been frozen successfully.")
    file_exists = os.path.exists(file_path)

    fieldnames = ["Name","Last_Name","Phone","Age","Gender","Country","State","Aadhar","Account_no","Ifsc_number","Balance","Date & Time","Status"]
    with open (file_path,"w",newline="",encoding="utf") as file:
        writer = csv.DictWriter(file,fieldnames=fieldnames)
        if not file_exists or os.path.getsize(file_path) == 0:
            writer.writeheader()
            writer.writerow({
                "Name": account["Name"], 
                "Last_Name": account["Last_Name"],
                "Phone": account["Phone"], 
                "Age": account["Age"], 
                "Gender": account["Gender"],
                "Country": account["Country"],
                "State" : account["State"],
                "Aadhar": account["Aadhar"], 
                "Account_no": account["Account_no"],
                "Ifsc_number" : account["Ifsc_number"],
                "Balance": account["Balance"],
                "Date & Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Status": "Frozen"
            })
    
    fieldnames = ["Name","Last_Name","Phone","Age","Gender","Country","State","Aadhar","Account_no","Ifsc_number","Balance","Status"]
    with open("Accounts.csv", "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        accounts = []
        for row in reader:
            if row["Account_no"] == account_no and row["Ifsc_number"] == ifsc_number:
                row["Status"] = "Frozen"
            accounts.append(row) 
    with open("Accounts.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(accounts)               



