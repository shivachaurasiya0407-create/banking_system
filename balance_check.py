from bank_system import Bank

def balance_check():
 bank = Bank()

 print("--- check balance ---") 
 account_no =input("Enter Account No.: ").strip()
 if not account_no.isdigit():
    print("Invalid Account Number")
    exit()
 account_no = int(account_no)
 account = bank.find_account(account_no)
 if account is None:
    print("Invalid Account Number")
    exit()
 print("\nAccount Details")
 print("Name       :",account["Name"])
 print("Account No.:",account["Account_no"])
 print("Balance    :",account["Balance"])


