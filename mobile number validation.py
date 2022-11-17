import re

m = input("Enter your mobile number")

r = re.fullmatch('[6-9][0-9]{9}',m) 

if r!=None: 
     print('Valid')
else:
     print('Invalid')