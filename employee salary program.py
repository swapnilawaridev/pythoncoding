Basic_salary = float(input("Enter Basic Salary"))
da = (float)(15 * Basic_salary) / 100.0
hra = (float)(10 * Basic_salary) / 100.0
other = (float)(3 * Basic_salary) / 100.0
gros_salary = Basic_salary + da + hra + other
print(
    "Your gross salary is {", Basic_salary, "} =", gros_salary)