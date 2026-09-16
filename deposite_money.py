from bank_system import Bank

def deposite_money():
 bank = Bank()

 print("--- Deposite Money ---") 
 account_no =input("Enter Account No.: ").strip()
 if not account_no.isdigit():
     print("Invalid Account Number")
     exit()
 account_no = int(account_no)

 try:      
     amount = int(input("Enter Deposite amount :"))
     if amount <= 0  :
         print("Invalid amount")
         exit()
 except ValueError: 
     print("Enter Amount is Digit") 
     exit()
 account = bank.find_account(account_no)
 if account is None:
     print("Account Not Find")
     exit()
 new_balance = float(account["Balance"]) + amount
 bank.update_balance(account_no,new_balance)
 bank.log_transaction(account_no, "Deposit", amount,0, new_balance)
 print("Deposited       :",amount)
 print("Current Balance :",new_balance)

# deposite = deposite_money() 
