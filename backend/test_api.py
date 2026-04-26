import requests
import json

# 测试AI分类接口
url = "http://localhost:8000/ai-classify"
headers = {"Content-Type": "application/json"}
data = {"user_input": "我的账户登录不上了，该怎么办？"}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
