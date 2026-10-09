from bank_system import Bank


def money_transfer():
    bank = Bank()
    print("--- Money Transfer ---")
    sender = input("Sender account number: ").strip()
    sender_ifsc = input("Sender IFSC: ").strip()
    receiver = input("Receiver account number: ").strip()
    receiver_ifsc = input("Receiver IFSC: ").strip()
    if (
        len(sender) != 10
        or not sender.isdigit()
        or len(receiver) != 10
        or not receiver.isdigit()
        or not sender_ifsc
        or not receiver_ifsc
    ):
        print("Enter valid 10-digit account numbers and IFSC codes.")
        return
    amount = input("Transfer amount (Rs.): ").strip()
    try:
        sender_balance, receiver_balance = bank.transfer(
            sender, sender_ifsc, receiver, receiver_ifsc, amount
        )
    except ValueError as error:
        print(error)
        return
    print("Transfer successful.")
    print(f"Sender balance: Rs. {sender_balance:.2f}")
    print(f"Receiver balance: Rs. {receiver_balance:.2f}")
