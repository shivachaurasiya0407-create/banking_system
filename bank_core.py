from bank_system import Bank
from balance_check import balance_check
from deposite_money import deposite_money
from withdraw_money import withdraw_money
from account_info import account_info
from transaction_history import transaction_history
from money_transfer import money_transfer
from employee import employee_login
from employee import employee_add
from account_freeze import freeze_account

class Core:
  def login_employee(self):
    return employee_login.login_employee()

  def balance_check(self):
    balance = balance_check()
    
#   Deposite money
  def deposite_money(self):
   deposite_money()

  # Withdraw money
  def withdraw_money(self):
    withdraw_money()
    
  # account info
  def account_info(self):
   account_info()

    # money transfer 
  def money_transfer(self):
   money_transfer()

  def transaction_history(self):
    transaction_history() 

  def employee_add(self):
    employee_add.add_employee()

  def freeze_account(self):
    freeze_account()
    