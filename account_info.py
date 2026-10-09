from bank_system import Bank


def account_info():
    bank = Bank()
    print("--- Account Info ---")
    account_no = input("Account number: ").strip()
    if len(account_no) != 10 or not account_no.isdigit():
        print("Enter a valid 10-digit account number.")
        return
    ifsc_number = input("IFSC number: ").strip()
    account = bank.find_account(account_no, ifsc_number)
    if account is None:
        print("Account not found.")
        return
    aadhar = account.get("Aadhar", "")
    masked_aadhar = f"{'*' * max(0, len(aadhar) - 4)}{aadhar[-4:]}" if aadhar else ""
    print("\nAccount Details")
    print("Name        :", f"{account['Name']} {account['Last_Name']}".strip())
    print("Phone       :", account["Phone"])
    print("Age         :", account["Age"])
    print("Gender      :", account["Gender"])
    print("Country     :", account["Country"])
    print("State       :", account["State"])
    print("Aadhaar     :", masked_aadhar)
    print("Account no. :", account["Account_no"])
    print("IFSC        :", account["Ifsc_number"])
    print("Balance     : Rs.", account["Balance"])
    print("Status      :", account["Status"])
