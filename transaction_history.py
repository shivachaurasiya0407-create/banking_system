from bank_system import Bank
import os
import csv

def transaction_history():
 bank = Bank()
 print("--- Transaction History ---")
 account_no = input("Enter Account No. :").strip()

 file_path = f"Transaction_history/{account_no}.csv"
 if not os.path.exists(file_path):
    print("No transaction history records found.")
    exit()

 print(f"\n{'TXN ID':<12} | {'Type':<12} | {'CR':<10} | {'DR':<10} | {'Balance':<10} | {'Date & Time'}")
 print("-" * 65)
 has_history = False
 with open(file_path, "r", newline="", encoding="utf-8") as file_2:
    reader = csv.DictReader(file_2)
    for row in reader:
       if row["Account_No"] == account_no:
          print(f"{row['Transaction_Id']:<12} | {row['Transaction_Type']:<12} | {row['CR']:<10} | {'DR':<10} | {row['Balance']:<10} | {row['Date']} {row['Time']}")
          has_history = True
          
 if not has_history:
    print("No transactions found for this account number.")

# transaction = transaction_history()     