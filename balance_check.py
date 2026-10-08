from bank_system import Bank

def balance_check():
 bank = Bank()

 print("--- check balance ---") 
 account_no =input("Enter Account No.: ").strip()
 ifsc_number = input("Enter IFSC Number: ").strip()
 
 if not account_no.isdigit():
    print("Invalid Account Number")
    return
 account_no = int(account_no)
 account = bank.find_account(account_no, ifsc_number,status = "Active")
 if account is None:
    print("Invalid Account Number and IFSC Number")
    return
 print("\nAccount Details")
 print("Name       :",account["Name"])
 print("Account No.:",account["Account_no"])
 print("Balance    :",account["Balance"])
 print("Ifsc Number:",account["Ifsc_number"])
 print("Status     :",account["Status"])


