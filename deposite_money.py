from bank_system import Bank


def deposite_money():
    bank = Bank()
    print("--- Deposit Money ---")
    account_no = input("Enter account number: ").strip()
    if len(account_no) != 10 or not account_no.isdigit():
        print("Enter a valid 10-digit account number.")
        return
    ifsc_number = input("Enter IFSC number: ").strip()
    if not ifsc_number:
        print("IFSC number is required.")
        return
    amount = input("Enter deposit amount (Rs.): ").strip()
    try:
        new_balance = bank.deposit(account_no, ifsc_number, amount)
    except ValueError as error:
        print(error)
        return
    print(f"Deposited: Rs. {amount}")
    print(f"Current balance: Rs. {new_balance:.2f}")
