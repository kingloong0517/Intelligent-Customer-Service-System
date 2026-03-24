import requests
import time

print("===== 新的注册和登录测试 =====")

BASE_URL = "http://localhost:8000"

def test_registration_and_login():
    print("\n1. 测试注册新用户...")
    
    # 生成随机用户名，避免重复
    username = f"testuser_new_{int(time.time())}"
    password = "123456"
    
    try:
        # 注册新用户
        register_url = f"{BASE_URL}/register"
        register_data = {
            "username": username,
            "password": password
        }
        
        print(f"注册用户: {username}")
        print(f"密码: {password}")
        
        register_response = requests.post(register_url, json=register_data)
        
        print(f"注册响应状态码: {register_response.status_code}")
        print(f"注册响应内容: {register_response.text}")
        
        if register_response.status_code == 200:
            print(f"✅ 注册成功！")
            
            # 测试登录
            print("\n2. 测试登录...")
            login_url = f"{BASE_URL}/login"
            login_data = {
                "username": username,
                "password": password
            }
            
            login_response = requests.post(login_url, data=login_data)
            
            print(f"登录响应状态码: {login_response.status_code}")
            print(f"登录响应内容: {login_response.text}")
            
            if login_response.status_code == 200:
                result = login_response.json()
                print(f"✅ 登录成功！")
                print(f"Token: {result['access_token']}")
                
                # 测试使用 Token 访问受保护接口
                print("\n3. 测试受保护接口 (/chat)...")
                chat_url = f"{BASE_URL}/chat"
                headers = {
                    "Authorization": f"Bearer {result['access_token']}"
                }
                chat_data = {
                    "user_input": "测试受保护接口"
                }
                
                chat_response = requests.post(chat_url, json=chat_data, headers=headers)
                
                print(f"聊天接口响应状态码: {chat_response.status_code}")
                print(f"聊天接口响应内容: {chat_response.text}")
                
                if chat_response.status_code == 200:
                    chat_result = chat_response.json()
                    print(f"✅ 受保护接口访问成功！")
                    print(f"AI 回复: {chat_result['reply']}")
                    return True
                else:
                    print(f"❌ 受保护接口访问失败")
                    return False
            else:
                print(f"❌ 登录失败")
                return False
        else:
            print(f"❌ 注册失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_registration_and_login()
    print("\n===== 测试完成 =====")