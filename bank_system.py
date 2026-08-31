import random 
import csv
import os
class Bank: 
  FILE ="Accounts.csv"     # File name
  def __init__(self): 
    self.balance = 0
      
  def create_account(self):   
    while True: 
      # Name Input
      self.name = input("Enter Name :").strip()

       # Phone Number input  
      while True: 
        self.phone = input("Phone No.:").strip()  
        if len(self.phone) == 10 and self.phone.isdigit():  
          break 
        print("Invalid Phone number")

      # Age input
      while True:
        try:  
           self.age = int(input("Age :"))  
           if self.age>=18: 
             break
           print("You Are Not Eligible to open Account (Must be 18+).\n") 
           return
        except ValueError:
          print("Enter Age in Digit")

      # Aadhaar Input
      while True:    
        self.aadhar_no = input("Aadhar (12 digit).:").strip()
        if len(self.aadhar_no) == 12 and self.aadhar_no.isdigit():
          if self.aadhar_exists(self.aadhar_no):
            print("Aadhaar number alredy exists")
            return
          break
        print("Invalid Aadhaar Number. Must be 12 digits.")

      # Account Number Generation
      while True:
        self.account_no = random.randint(1000000000,9999999999) 
        if not self.account_exists(self.account_no) :
          break
      print("Account is sucessfull Created Account No.:",self.account_no) 

      # Deposite Input
      while True:
        try:
           amount = int(input("Deposite Amt.:")) 
           if amount>= 2000 :
             break 
           print("Minimum deposite is Rs.2000") 
        except ValueError :
          print("Enter Amount in digit")
      self.balance = amount 

      # 7. Write to CSV file
      file_exists = os.path.exists(self.FILE)
      fieldnames = ["Name","Phone","Age","Aadhar","Account_no","Balance"]

      with open(self.FILE, "a",newline="",encoding="utf-8") as file:
       
       writer = csv.DictWriter(file,fieldnames=fieldnames) 
       if not file_exists or os.path.getsize(self.FILE) == 0:
          writer.writeheader()
       writer.writerow({
                "Name": self.name, 
                "Phone": self.phone, 
                "Age": self.age, 
                "Aadhar": self.aadhar_no, 
                "Account_no": self.account_no, 
                "Balance": self.balance
            })
      print("\n Account Details :")
      print("Name        :",self.name)
      print("Phone       :",self.phone)
      print("Age         :",self.age)
      print("Aadhar No.  :",self.aadhar_no)
      print("Account no. :",self.account_no)
      print("Balance     :",self.balance)
      break

  def aadhar_exists(self,aadhar_no):
    if not os.path.exists(self.FILE):
      return False

    with open(self.FILE,"r",newline="",encoding="utf-8") as file:
      reader = csv.DictReader(file)
      for row in reader:
        if row["Aadhar"] == str(aadhar_no).strip():
          return True
    return False    
     
  def account_exists(self,account_no):
    if not os.path.exists(self.FILE):
      return False
    
    with open(self.FILE,"r",newline="",encoding="utf-8") as file:
      reader =csv.DictReader(file)
      for row in reader:
        if row["Account_no"] == str(account_no).strip():
            return True
    return False
  
  def find_account(self,account_no):
      if not os.path.exists(self.FILE):
         return None

      with open(self.FILE,"r",newline="",encoding="utf-8") as file:
        reader =csv.DictReader(file)
        for row in reader:
          if row["Account_no"] == str(account_no).strip():
              return row
      return None

   #Balance Check     
  def balance_check(self): 
      account_no =input("Enter Account No.: ").strip()
      if not account_no.isdigit():
        print("Invalid Account Number")
        return
      account_no = int(account_no)
      account = self.find_account(account_no)
      if account is None:
        print("Invalid Account Number")
        return
      print("\nAccount Details")
      print("Name       :",account["Name"])
      print("Account No.:",account["Account_no"])
      print("Balance    :",account["Balance"])

  # Deposite money
  def deposite_money(self): 
    account_no =input("Enter Account No.: ").strip()
    if not account_no.isdigit():
      print("Invalid Account Number")
      return
    account_no = int(account_no)

    try:      
      amount = int(input("Enter Deposite amount"))
      if amount <= 0  :
        print("Invalid amount")
        return
    except ValueError: 
      print("Enter Amount is Digit") 
      return
    account = self.find_account(account_no)
    if account is None:
      print("Account Not Find")
      return
    new_balance = float(account["Balance"]) + amount
    self.update_balance(account_no,new_balance)
    print("Deposited       :",amount)
    print("Current Balance :",new_balance)

    # Withdraw money
  def withdraw_money(self):
    account_no = input("Enter Account No.:").strip()
    if not account_no.isdigit():
      print("Invalid Account number")
      return
    account_no = int(account_no)

    try:
      amount = int(input("Enter Withdraw Amount :"))
      if amount <= 0:
        print("Invalid Amount")
        return
    except ValueError:
      print("Enter Amount in digit")
      return    

    account =self.find_account(account_no)
    if account is None:
      print("Invalid Account Number")
      return
    current_balance = float(account["Balance"])
    if amount > current_balance:
      print("Insufficient Balance")
      return
    new_balance = current_balance - amount
    self.update_balance(account_no,new_balance)
    print("Withdrawn      :",amount)
    print("Current Balance :",new_balance) 

    # Balance update in csv file
  def update_balance(self,account_no,new_balance):
    accounts = []  
    if not os.path.exists(self.FILE):
      return
    
    with open(self.FILE,"r",newline="",encoding="utf-8") as file:
      reader = csv.DictReader(file)
      for row in reader:
        if row["Account_no"] == str(account_no).strip():
          row["Balance"] = str(new_balance)
        accounts.append(row)
    fieldnames = ["Name","Phone","Age","Aadhar","Account_no","Balance"]    

    with open(self.FILE,"w",newline="",encoding="utf-8") as file:
      writer = csv.DictWriter(file,fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(accounts)


    
bank_obj = Bank() 
print("=" * 60)
print(f"{'BANKING SYSTEM':^60}")
print("=" * 60)
while True :
  
  print("------ Our Services ------ \n1.Account Open\n2.Check Balance\n3.Deposite Money\n4.Withdraw Money\n5.Exit")
  try:
    service = int(input("Choose Service :"))

  except ValueError:
    print("Pleace Enter a Number")
    continue  
  if service == 1: 
    print("\n--- Account Opening ---") 
    bank_obj.create_account() 
   
  elif service == 2: 
    bank_obj.balance_check() 
    
  elif service == 3: 
    print("\n --- Deposite Money ---") 
    bank_obj.deposite_money() 
   
  elif service == 4: 
    print("\n --- Withdraw Money ---") 
    bank_obj.withdraw_money() 

  elif service == 5: 
   print(" ====== Thank you for using our bank ======")
   break 
  else: 
   print("Invalid service")