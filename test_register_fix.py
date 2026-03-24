import requests
import time

print("===== 注册接口修复测试 =====")

BASE_URL = "http://localhost:8000"

def test_register():
    print("\n测试注册接口...")
    
    # 生成随机用户名，避免重复
    username = f"testuser_{int(time.time())}"
    # 使用非常短的密码测试
    password = "123456"
    
    try:
        url = f"{BASE_URL}/register"
        data = {
            "username": username,
            "password": password
        }
        
        print(f"注册用户: {username}")
        print(f"密码: {password} (长度: {len(password)} 字符)")
        print(f"发送请求数据: {data}")
        
        response = requests.post(url, json=data)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 注册成功！")
            print(f"用户信息: {result}")
            return True
        else:
            print(f"❌ 注册失败，状态码：{response.status_code}")
            print(f"错误信息：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 注册异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_register()
    print("\n===== 测试完成 =====")