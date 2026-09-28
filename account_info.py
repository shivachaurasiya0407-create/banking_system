from bank_system import Bank

def account_info():
 bank = Bank()
 print("--- Account Info ---")
 account_no = input("Account Number :").strip()
 ifsc_number = input("IFSC Number :").strip()
 if not account_no.isdigit():
    print("Invalid Account number and onl digit allow")
    return 
    
 account_no = int(account_no)
 account = bank.find_account(account_no, ifsc_number)
 if account is None:
    print("Account number or IFSC number not exists") 
    return
 print("\n Account Details :")
 print("Name        :",account["Name"])
 print("Phone       :",account["Phone"])
 print("Age         :",account["Age"])
 print("Gender      :",account["Gender"])
 print("Country     :",account["Country"])
 print("State       :",account["State"])
 print("Aadhar No.  :",account["Aadhar"])
 print("Account no. :",account["Account_no"])
 print("Ifsc Number :",account["Ifsc_number"])
 print("Balance     :",account["Balance"])
