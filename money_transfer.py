from bank_system import Bank  

def money_transfer():
 bank = Bank()
 print("--- Money Transfer ---")
 sender = input("Sender Account No. :").strip()
 receiver = input("Receiver Account No. :").strip()
 amount = float(input("Enter Send Amount: ").strip())

 sender_account = bank.find_account(sender)
 receiver_account = bank.find_account(receiver)
        
 if sender_account is  None :
    print("Invalid Sender Account")
    exit()
 if receiver_account is None :
    print("Invalid Receiver Account")
    exit()
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

# money = money_transfer()    
      

 

    


        
    
