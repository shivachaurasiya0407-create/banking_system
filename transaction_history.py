import csv

from bank_system import Bank


def transaction_history():
    bank = Bank()
    print("--- Transaction History ---")
    account_no = input("Account number: ").strip()
    if len(account_no) != 10 or not account_no.isdigit():
        print("Enter a valid 10-digit account number.")
        return
    ifsc_number = input("IFSC number: ").strip()
    if bank.find_account(account_no, ifsc_number) is None:
        print("Account not found.")
        return
    file_path = bank.history_dir / f"{account_no}.csv"
    if not file_path.exists():
        print("No transaction history records found.")
        return
    print(
        f"\n{'TXN ID':<18} | {'TYPE':<16} | {'CREDIT':<12} | "
        f"{'DEBIT':<12} | {'BALANCE':<12} | DATE & TIME"
    )
    print("-" * 100)
    has_history = False
    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            row_ifsc = row.get("Ifsc_Number")
            if (
                row.get("Account_No", "").strip() != account_no
                or (row_ifsc and row_ifsc.strip().casefold() != ifsc_number.casefold())
            ):
                continue
            print(
                f"{row.get('Transaction_Id', ''):<18} | "
                f"{row.get('Transaction_Type', ''):<16} | "
                f"{row.get('CR', '0'):<12} | {row.get('DR', '0'):<12} | "
                f"{row.get('Balance', ''):<12} | "
                f"{row.get('Date', '')} {row.get('Time', '')}"
            )
            has_history = True
    if not has_history:
        print("No transactions found for this account.")
