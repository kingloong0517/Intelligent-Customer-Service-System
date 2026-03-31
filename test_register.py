import requests
import json

# 测试1: 注册已存在的用户名
print("=== 测试1: 注册已存在的用户名 ===")
url = "http://localhost:8000/register"
headers = {"Content-Type": "application/json"}
data = {"username": "testuser", "password": "testpassword"}

try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"注册接口状态码: {response.status_code}")
    print(f"注册接口响应: {response.text}")
except Exception as e:
    print(f"测试失败: {str(e)}")

# 测试2: 注册新用户名
print("\n=== 测试2: 注册新用户名 ===")
data = {"username": "testuser_new", "password": "testpassword"}

try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"注册接口状态码: {response.status_code}")
    print(f"注册接口响应: {response.text}")
except Exception as e:
    print(f"测试失败: {str(e)}")

# 测试3: 登录新注册的用户
print("\n=== 测试3: 登录新注册的用户 ===")
url = "http://localhost:8000/login"
headers = {"Content-Type": "application/x-www-form-urlencoded"}
data = {"username": "testuser_new", "password": "testpassword"}

try:
    response = requests.post(url, headers=headers, data=data)
    print(f"登录接口状态码: {response.status_code}")
    print(f"登录接口响应: {response.text}")
except Exception as e:
    print(f"登录测试失败: {str(e)}")
