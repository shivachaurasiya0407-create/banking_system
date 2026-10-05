def freeze_account():
    print(" ======= Freeze Account =======")
    account_number = input("Enter Account Number to freeze: ")
    if not account_number.isdigit:
        print("Enter Account number in digit")
    # Implement the logic to freeze the account here
    print(f"Account {account_number} has been frozen successfully.")