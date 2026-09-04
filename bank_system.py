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
      while True:
        self.name = str(input("Enter Name :")).upper()
        for i in self.name:
          if not i.isalpha() and i != " ":
            print("Special character found :",i)
            break
        else:
          print("Valid Name")
          break  
      
       # Phone Number input  
      while True: 
        self.phone = input("Phone No.:").strip()  
        if len(self.phone) == 10 and self.phone.isdigit():  
          break 
        print("Enter Only Digit and  10 Digit Phone number")

        # gender choise
      while True:
        select_gender =   input("Select Gender\n1.Male\n2.Female\n3.Other\nOption :").strip().lower()
        if select_gender == "1" or select_gender == "male":
          self.gender = "Male"
          break
        elif select_gender == "2" or select_gender == "female":
          self.gender ="Female"
          break
        elif select_gender == "3" or select_gender == "other":
          self.gender ="Other"
          break     
        else:
          print("Invlid Choise")
          
               
      # Age input
      while True:
        try:  
           self.age = int(input("Age :"))  
           if self.age>=18 and self.age <=110:
             break
           print("You Are Not Eligible to open Account (Must be 18+) & wrong age\n") 
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
        print("Invalid Aadhaar Number. Must be 12 digits.or only number")

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
      fieldnames = ["Name","Phone","Age","Gender","Aadhar","Account_no","Balance"]

      with open(self.FILE, "a",newline="",encoding="utf-8") as file:
       
       writer = csv.DictWriter(file,fieldnames=fieldnames) 
       if not file_exists or os.path.getsize(self.FILE) == 0:
          writer.writeheader()
       writer.writerow({
                "Name": self.name, 
                "Phone": self.phone, 
                "Age": self.age, 
                "Gender": self.gender,
                "Aadhar": self.aadhar_no, 
                "Account_no": self.account_no, 
                "Balance": self.balance
            })
      print("\n Account Details :")
      print("Name        :",self.name)
      print("Phone       :",self.phone)
      print("Age         :",self.age)
      print("Gender      :",self.gender)
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

   # account info 
  def account_info(self):
    account_no = input("Account Number :")
    if not account_no.isdigit():
      print("Invalid Account number and onl digit allow")
      return 
    
    account_no = int(account_no)
    account = self.find_account(account_no)
    if account is None:
      print("Account number not exists") 
      return
    print("\n Account Details :")
    print("Name        :",account["Name"])
    print("Phone       :",account["Phone"])
    print("Age         :",account["Age"])
    print("Gender      :",account["Gender"])
    print("Aadhar No.  :",account["Aadhar"])
    print("Account no. :",account["Account_no"])
    print("Balance     :",account["Balance"])
    
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
    fieldnames = ["Name","Phone","Gender","Age","Aadhar","Account_no","Balance"]    

    with open(self.FILE,"w",newline="",encoding="utf-8") as file:
      writer = csv.DictWriter(file,fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(accounts)


    
bank_obj = Bank() 
print("=" * 60)
print(f"{'BANKING SYSTEM':^60}")
print("=" * 60)
while True :
  
  print("------ Our Services ------ \n1.Account Open\n2.Check Balance\n3.Deposite Money\n4.Withdraw Money\n5.Account info\n6.Exit")
  try:
    service = input("Choose Service :").strip().lower()

  except ValueError:
    print("Pleace Enter a Number")
    continue  
  if service == "1" or service == "account open": 
    print("\n--- Account Opening ---") 
    bank_obj.create_account() 
   
  elif service == "2" or service == "check balance": 
    bank_obj.balance_check() 
    
  elif service == "3" or service == "deposite money": 
    print("\n --- Deposite Money ---") 
    bank_obj.deposite_money() 
   
  elif service == "4" or service == "withdraw money": 
    print("\n --- Withdraw Money ---") 
    bank_obj.withdraw_money() 

  elif service =="5" or service == "account info":
    bank_obj.account_info()  

  elif service == "6" or service == "exit": 
   print(" ====== Thank you for using our bank ======")
   break 
  else: 
   print("Invalid service")