from bank_system import Bank


def balance_check():
    bank = Bank()
    print("--- Check Balance ---")
    account_no = input("Enter account number: ").strip()
    if len(account_no) != 10 or not account_no.isdigit():
        print("Enter a valid 10-digit account number.")
        return
    ifsc_number = input("Enter IFSC number: ").strip()
    account = bank.find_account(account_no, ifsc_number, status="Active")
    if account is None:
        print("Active account not found.")
        return
    print("\nAccount Details")
    print("Name       :", account["Name"])
    print("Account No.:", account["Account_no"])
    print("Balance    : Rs.", account["Balance"])
    print("IFSC       :", account["Ifsc_number"])
