import json

x = '{"age":54, "weight": 62}'
y = json.loads(x)
print(y)
print(y['age'])
print(y['weight'])