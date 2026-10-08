from bank_system import Bank  

def money_transfer():
   bank = Bank()
   print("--- Money Transfer ---")
   sender = input("Sender Account No. :").strip()
   sender_ifsc = input("Sender IFSC Number :").strip()
   receiver = input("Receiver Account No. :").strip()
   receiver_ifsc = input("Receiver IFSC Number :").strip()
   amount = float(input("Enter Send Amount: ").strip())

   sender_account = bank.find_account(sender, sender_ifsc,status="Active")
   receiver_account = bank.find_account(receiver, receiver_ifsc,status="Active")
        
   if sender_account is  None and bank.find_account(sender, sender_ifsc, status="Active") is None:
      print("Invalid Sender Account & Sender Account is not Active")
      return
   if receiver_account is None and bank.find_account(receiver, receiver_ifsc, status="Active") is None:
      print("Invalid Receiver Account & Receiver Account is not Active")
      return
   sender_balance = float(sender_account["Balance"])

   if amount <= 0 :
      print("Invalid Amount") 
   elif amount > sender_balance:
    print("Insufficient balance")
   else:
      new_sender_balance = sender_balance - amount
      new_receiver_balance = float(receiver_account["Balance"]) + amount
      bank.update_balance(sender,new_sender_balance)
      bank.update_balance(receiver,new_receiver_balance) 
      bank.log_transaction(sender,receiver,0,amount,new_sender_balance)
      bank.log_transaction(receiver,sender,amount,0,new_receiver_balance) 
      print("Transfer Sucessfull")    


