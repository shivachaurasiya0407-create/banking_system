from bank_system import Bank

def account_info():
 bank = Bank()
 print("--- Account Info ---")
 account_no = input("Account Number :").strip()
 if not account_no.isdigit():
    print("Invalid Account number and onl digit allow")
    exit() 
    
 account_no = int(account_no)
 account = bank.find_account(account_no)
 if account is None:
    print("Account number not exists") 
    exit()
 print("\n Account Details :")
 print("Name        :",account["Name"])
 print("Phone       :",account["Phone"])
 print("Age         :",account["Age"])
 print("Gender      :",account["Gender"])
 print("Aadhar No.  :",account["Aadhar"])
 print("Account no. :",account["Account_no"])
 print("Balance     :",account["Balance"])

# account =account_info() 