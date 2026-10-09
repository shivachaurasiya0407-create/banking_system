from account_freeze import freeze_account, unfreeze_account
from account_info import account_info
from balance_check import balance_check
from deposite_money import deposite_money
from employee import employee_add, employee_login
from money_transfer import money_transfer
from transaction_history import transaction_history
from withdraw_money import withdraw_money


class Core:
    def login_employee(self):
        return employee_login.login_employee()

    def balance_check(self):
        balance_check()

    def deposite_money(self):
        deposite_money()

    def withdraw_money(self):
        withdraw_money()

    def account_info(self):
        account_info()

    def money_transfer(self):
        money_transfer()

    def transaction_history(self):
        transaction_history()

    def employee_add_remove(self):
        print("======= Add Employee / Remove Employee =======")
        action = input("Enter 'add' or 'remove': ").strip().lower()
        if action == "add":
            employee_add.add_employee()
        elif action == "remove":
            employee_add.employee_remove()
        else:
            print("Invalid employee action.")

    def view_employees(self):
        employee_add.view_employees()

    def change_employee_password(self):
        employee_add.change_employee_password()

    def freeze_unfreeze_account(self):
        print("======= Freeze / Unfreeze Account =======")
        action = input("Enter 'freeze' or 'unfreeze': ").strip().lower()
        if action == "freeze":
            freeze_account()
        elif action == "unfreeze":
            unfreeze_account()
        else:
            print("Invalid account action.")
