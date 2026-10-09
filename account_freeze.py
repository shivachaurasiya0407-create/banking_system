from bank_system import Bank


def _change_account_status(status, action_label):
    bank = Bank()
    print(f"======= {action_label} Account =======")
    account_no = input("Account number (10 digits): ").strip()
    if len(account_no) != 10 or not account_no.isdigit():
        print("Enter a valid 10-digit account number.")
        return
    ifsc_number = input("IFSC code: ").strip()
    if not ifsc_number:
        print("IFSC code is required.")
        return
    try:
        bank.set_account_status(account_no, ifsc_number, status)
    except ValueError as error:
        print(error)
        return
    print(f"Account {account_no} is now {status.lower()}.")


def freeze_account():
    _change_account_status("Frozen", "Freeze")


def unfreeze_account():
    _change_account_status("Active", "Unfreeze")
