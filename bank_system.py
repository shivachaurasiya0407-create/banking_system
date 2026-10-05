import random 
from difflib import get_close_matches
import csv
import os
from datetime import datetime
import uuid
class Bank: 
  FILE ="Accounts.csv"   # File name
  bank_code = "SHIV"  

  def __init__(self): 
    self.balance = 0
    self.branch_number = 1
      
  def create_account(self):   
    if not os.path.exists("Transaction_history"):
      os.makedirs("Transaction_history")

    while True: 
      while True:
        print("\n--- Account Opening ---")
        self.name = str(input("Enter Name :")).upper()
        self.last_name = str(input("Enter Name :")).upper()

        for i in self.name and self.last_name:
          if not i.isalpha() and i != " ":
            print("Special character found :",i)
            break
        else:
          # print("Valid Name")
          break  
      
       # Phone Number input  
      while True: 
        self.phone = input("Phone No.:").strip()  
        is_valid = True if len(self.phone) == 10 and self.phone.isdigit() else print("Enter Only Digit and  10 Digit Phone number")   
        if is_valid :break 
        
        # gender choise
      while True:
          select_gender =   input("Select Gender\n1.Male\n2.Female\n3.Other\nOption :").strip().lower()
          self.gender = ("Male" if select_gender in( "1","male") else "Female" if select_gender in ("2","female") else "Other" if select_gender in ("3","other")else None)                  
          if self.gender:
            break
          print("Invalid Choise")
               
      # Age input
      while True:
        try:  
           self.age = int(input("Age :"))  
           valid_age = True if self.age>=18 and self.age <=110 else  print("You Are Not Eligible to open Account (Must be 18+) & wrong age\n")
           if valid_age:
             break
           if not valid_age :
             return
        except ValueError:
          print("Enter Age in Digit")

      #country
      while True:
         
        country_list = ["India"]

        self.country_input = input("Country :")
        for country in country_list:
              if country == self.country_input.lower():
                  return country
        matches_c = get_close_matches(self.country_input,country_list,n=1,cutoff=0.75)
        if matches_c:
            # return matches_c[0]
            print("Matched Country:",matches_c[0])
            break
        else:
          print("Invalid Country")
      
      #state    
      while True: 
        india_state = ["Andaman and Nicobar Islands","Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Dadra and nagar Haveli and Damanand Diu","Delhi","Goa","Gujarat","Haryana","Himachal Pradesh","Jammu and Kashmir","Jharkhand","Karnataka","Kerala","Ladakh","Lakshadweep","Madhy Pradesh","Maharashtra","Manipur","Meghalaya","Mizora","Nagaland","Odisha","Puducherry","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West bengal"]    
        
        self.state_input = input("State :").lower()
        for state in india_state:
          if state == self.state_input:
              return state        
        matches = get_close_matches(self.state_input,india_state,n=1,cutoff=0.75)
        if matches:
            print("Matched State:",matches[0])
            break
        else:
          print("Invalid State")
        

      # Aadhaar Input
      while True:    
        self.aadhar_no = input("Aadhar (12 digit).:").strip()
        valid_aadhar =True if len(self.aadhar_no) == 12 and self.aadhar_no.isdigit() else print("Invalid Aadhaar Number. Must be 12 digits.or only number")
        if valid_aadhar:
          if self.aadhar_exists(self.aadhar_no):
            print("Aadhaar number alredy exists")
            return
          break
        
      # Account Number Generation
      while True:
        self.account_no = random.randint(1000000000,9999999999)
        self.code = f"{self.branch_number : 06d}" 
        self.branch_number += 1
        self.ifsc = f"{self.bank_code}0{self.code}" 
        if not self.account_exists(self.account_no) and not self.ifsc_exists(self.ifsc):
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
      fieldnames = ["Name","Last_Name","Phone","Age","Gender","Country","State","Aadhar","Account_no","Ifsc_number","Balance"]

      with open(self.FILE, "a",newline="",encoding="utf-8") as file:
       
       writer = csv.DictWriter(file,fieldnames=fieldnames) 
       if not file_exists or os.path.getsize(self.FILE) == 0:
          writer.writeheader()
       writer.writerow({
                "Name": self.name, 
                "Last_Name": self.last_name,
                "Phone": self.phone, 
                "Age": self.age, 
                "Gender": self.gender,
                "Country": matches_c[0],
                "State" : matches[0],
                "Aadhar": self.aadhar_no, 
                "Account_no": self.account_no,
                "Ifsc_number" : self.ifsc, 
                "Balance": self.balance
            })
       
      self.log_transaction(self.account_no, "Deposit", amount,0, self.balance)

      print("\n Account Details :")
      print("Name        :",self.name)
      print("Last Name   :",self.last_name)
      print("Phone       :",self.phone)
      print("Age         :",self.age)
      print("Gender      :",self.gender)
      print("Country     :",matches_c[0])
      print("State       :",matches[0])
      print("Aadhar No.  :",self.aadhar_no)
      print("Account no. :",self.account_no)
      print("Ifsc_number :",self.ifsc)
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

  def ifsc_exists(self,ifsc_number):
      if not os.path.exists(self.FILE):
        return False
      
      with open(self.FILE,"r",newline="",encoding="utf-8") as file:
        reader =csv.DictReader(file)
        for row in reader:
          if row["Ifsc_number"] == str(ifsc_number).strip():
              return True
      return False
  
  def find_account(self,account_no, ifsc_number):
      if not os.path.exists(self.FILE):
         return None

      with open(self.FILE,"r",newline="",encoding="utf-8") as file:
        reader =csv.DictReader(file)
        for row in reader:
          if row["Account_no"] == str(account_no).strip() and row["Ifsc_number"] == str(ifsc_number ).strip():
              return row
      return None

    
  def log_transaction(self, account_no,txn_type, cr,dr, balance):
    file_path =f"Transaction_history/{account_no}.csv"

    txn_id = "TXN" + uuid.uuid4().hex[:8].upper()
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    file_exists = os.path.exists(file_path)
    fieldnames = ["Transaction_Id", "Account_No", "Date", "Time", "Transaction_Type", "CR","DR", "Balance"]

    with open(file_path, "a", newline="", encoding="utf-8") as file_2:
      writer = csv.DictWriter(file_2, fieldnames=fieldnames)
      if not file_exists or os.path.getsize(file_path) == 0:
        writer.writeheader()
      writer.writerow({
          "Transaction_Id": txn_id,
          "Account_No": account_no,
          "Date": date_str,
          "Time": time_str,
          "Transaction_Type": txn_type,
          "CR": cr,
          "DR": dr,
          "Balance": balance
      })  

    
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
    fieldnames = ["Name","Last_Name","Phone","Age","Gender","Country","State","Aadhar","Account_no","Ifsc_number","Balance"]    

    with open(self.FILE,"w",newline="",encoding="utf-8") as file:
      writer = csv.DictWriter(file,fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(accounts)