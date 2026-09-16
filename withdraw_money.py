from bank_system import Bank

def withdraw_money():
 bank = Bank()
 print("--- Withdraw money")
 account_no = input("Enter Account No.:").strip()
 if not account_no.isdigit():
    print("Invalid Account number")
    exit()
 account_no = int(account_no)

 try:
     amount = int(input("Enter Withdraw Amount :"))
     if amount <= 0:
        print("Invalid Amount")
        exit()
 except ValueError:
     print("Enter Amount in digit")
     exit()    

 account =bank.find_account(account_no)
 if account is None:
    print("Invalid Account Number")
    exit()
 current_balance = float(account["Balance"])
 if amount > current_balance:
    print("Insufficient Balance")
    exit()
 new_balance = current_balance - amount
 bank.update_balance(account_no,new_balance)
 bank.log_transaction(account_no, "Withdrawal", 0,amount , new_balance)
 print("Withdrawn      :",amount)
 print("Current Balance :",new_balance)

# withdraw = withdraw_money() 
