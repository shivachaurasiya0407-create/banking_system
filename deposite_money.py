from bank_system import Bank

def deposite_money():
 bank = Bank()

 print("--- Deposite Money ---") 
 account_no =input("Enter Account No.: ").strip()
 ifsc_number = input("Enter IFSC Number: ").strip()
 if not account_no.isdigit():
     print("Invalid Account Number")
     exit()
 account_no = int(account_no)
 if not ifsc_number:
     print("Invalid IFSC Number")
     return

 try:      
     amount = int(input("Enter Deposite amount :"))
     if amount <= 0  :
         print("Invalid amount")
         return
 except ValueError: 
     print("Enter Amount is Digit") 
     return
 account = bank.find_account(account_no, ifsc_number,status="Active")
 if account is None:
     print("Account Not Found or account not active")
     return
 new_balance = float(account["Balance"]) + amount
 bank.update_balance(account_no,new_balance)
 bank.log_transaction(account_no, " Case Deposit", amount,0, new_balance)
 print("Deposited       :",amount)
 print("Current Balance :",new_balance) 
