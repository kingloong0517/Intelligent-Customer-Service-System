import requests
import json

# 测试AI分类接口，发送一个关于订单的问题
url = "http://localhost:8000/ai-classify"
headers = {"Content-Type": "application/json"}
data = {"user_input": "我的订单什么时候发货？"}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
