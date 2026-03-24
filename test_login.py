import requests
import time

print("===== 登录接口测试 =====")

BASE_URL = "http://localhost:8000"

def test_login():
    print("\n测试登录接口...")
    
    # 使用刚才注册的用户信息
    username = "testuser_1774171375"
    password = "123456"
    
    try:
        url = f"{BASE_URL}/login"
        # OAuth2PasswordRequestForm 需要表单数据格式
        data = {
            "username": username,
            "password": password
        }
        
        print(f"登录用户: {username}")
        print(f"密码: {password}")
        
        response = requests.post(url, data=data)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 登录成功！")
            print(f"Token: {result['access_token']}")
            
            # 测试使用 Token 访问受保护接口
            test_protected_api(result['access_token'])
            
            return True
        else:
            print(f"❌ 登录失败，状态码：{response.status_code}")
            print(f"错误信息：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 登录异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_protected_api(token):
    print("\n测试受保护接口 (/chat)...")
    
    try:
        url = f"{BASE_URL}/chat"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        data = {
            "user_input": "测试受保护接口"
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 受保护接口访问成功！")
            print(f"AI 回复: {result['reply']}")
            return True
        else:
            print(f"❌ 受保护接口访问失败，状态码：{response.status_code}")
            print(f"错误信息：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 受保护接口访问异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_login()
    print("\n===== 测试完成 =====")