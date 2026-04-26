import requests

# 测试会话列表接口
url = "http://localhost:8000/conversations"
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMTExIiwiZXhwIjoxNzc3MTg4ODI4fQ.NoeHkpONEHIdvzF-32kndMPtnMgFQhbX-me5qrgP7FU"
}

response = requests.get(url, headers=headers)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
