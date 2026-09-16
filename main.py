from bank_system import Bank
from bank_core import Core
 
   
if __name__ == "__main__": 
 bank_obj = Bank()
 core = Core()
 print("=" * 60)
 print(f"{'BANKING SYSTEM':^60}")
 print("=" * 60)
 services = {"1" : bank_obj.create_account,"account open" : bank_obj.create_account,
             "2" : core.balance_check,"check balance" : core.balance_check,
             "3" : core.deposite_money,"deposite money" : core.deposite_money,
             "4" : core.withdraw_money,"withdraw money" : core.withdraw_money,
             "5" : core.account_info,"account info" : core.account_info,
             "6" : core.transaction_history,"transaction history" : core.transaction_history,
             "7" : core.money_transfer,"fund transfer" : core.money_transfer}

menu = """------ Our Services ------ 
1.Account Open
2.Check Balance
3.Deposite Money
4.Withdraw Money
5.Account info
6.Transaction History
7.Money Transfer
8.Exit"""

while True :
   print(menu)
   service = input("Enter Service :").strip().lower()
   if service in ("8","exit"):
     print(" ======= Thank you for using our bank =======")
     break
   action = services.get(service)
   if action:
     action()
   else:
     print("Invalid Service! Please enter a valid option.\n")  

   
#  bank_obj = Bank() 
