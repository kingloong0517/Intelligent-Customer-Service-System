import requests
import time

print("===== AI 聊天系统测试 ======")

# 后端 API 地址
BASE_URL = "http://localhost:8000"

# 1. 测试发送消息
def test_send_message():
    print("\n1. 测试发送消息...")
    try:
        url = f"{BASE_URL}/chat"
        data = {"user_input": "你好，我是测试用户"}
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 发送消息成功！")
            print(f"   用户输入: {data['user_input']}")
            print(f"   AI 回复: {result['reply']}")
            return True
        else:
            print(f"❌ 发送消息失败，状态码：{response.status_code}")
            print(f"   错误信息：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 发送消息异常：{str(e)}")
        return False

# 2. 测试获取聊天记录
def test_get_history():
    print("\n2. 测试获取聊天记录...")
    try:
        url = f"{BASE_URL}/history"
        response = requests.get(url)
        
        if response.status_code == 200:
            history = response.json()
            print(f"✅ 获取聊天记录成功！")
            print(f"   总记录数: {len(history)}")
            
            if history:
                print("\n   最新的聊天记录：")
                for i, record in enumerate(history[:2]):  # 只显示前2条
                    print(f"\n   记录 #{record['id']}:")
                    print(f"   用户输入: {record['user_input']}")
                    print(f"   AI 回复: {record['ai_reply']}")
                    print(f"   时间: {record['timestamp']}")
            return True
        else:
            print(f"❌ 获取聊天记录失败，状态码：{response.status_code}")
            print(f"   错误信息：{response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 获取聊天记录异常：{str(e)}")
        return False

# 3. 测试原有的 messages 接口（保持兼容）
def test_get_messages():
    print("\n3. 测试兼容的 messages 接口...")
    try:
        url = f"{BASE_URL}/messages"
        response = requests.get(url)
        
        if response.status_code == 200:
            messages = response.json()
            print(f"✅ messages 接口调用成功！")
            print(f"   总记录数: {len(messages)}")
            return True
        else:
            print(f"❌ messages 接口调用失败，状态码：{response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ messages 接口异常：{str(e)}")
        return False

# 运行测试
if __name__ == "__main__":
    print(f"后端服务地址: {BASE_URL}")
    print(f"前端服务地址: http://localhost:3000")
    
    # 等待服务完全启动
    time.sleep(2)
    
    # 运行所有测试
    test_send_message()
    test_get_history()
    test_get_messages()
    
    print("\n===== 测试完成 ======")
    print("\n您可以在浏览器中访问以下地址：")
    print("- 前端聊天界面：http://localhost:3000")
    print("- 后端 API 文档：http://localhost:8000/docs")
    print("\n使用说明：")
    print("1. 打开前端页面 http://localhost:3000")
    print("2. 在输入框中输入消息，点击发送")
    print("3. 查看 AI 回复")
    print("4. 所有聊天记录会自动保存")
    print("5. 可以通过后端 API 获取历史记录")