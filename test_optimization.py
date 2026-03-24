import requests
import time

print("===== 测试聊天系统优化 ====")

BASE_URL = "http://localhost:8000"

def register_user(username, password):
    """注册用户"""
    url = f"{BASE_URL}/register"
    data = {
        "username": username,
        "password": password
    }
    response = requests.post(url, json=data)
    return response

def login_user(username, password):
    """登录用户"""
    url = f"{BASE_URL}/login"
    data = {
        "username": username,
        "password": password
    }
    response = requests.post(url, data=data)
    return response

def send_chat_message(token, message):
    """发送聊天消息"""
    url = f"{BASE_URL}/chat"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    data = {
        "user_input": message
    }
    response = requests.post(url, json=data, headers=headers)
    return response

def get_chat_history(token):
    """获取聊天历史"""
    url = f"{BASE_URL}/history"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    return response

def test_optimization():
    print("\n1. 注册两个测试用户...")
    
    # 注册用户1
    user1_username = f"user1_{int(time.time())}"
    user1_password = "123456"
    user1_register = register_user(user1_username, user1_password)
    print(f"用户1注册状态: {user1_register.status_code}")
    
    # 注册用户2
    user2_username = f"user2_{int(time.time())}"
    user2_password = "123456"
    user2_register = register_user(user2_username, user2_password)
    print(f"用户2注册状态: {user2_register.status_code}")
    
    if user1_register.status_code != 200 or user2_register.status_code != 200:
        print("❌ 注册失败")
        return False
    
    print("\n2. 两个用户登录...")
    
    # 用户1登录
    user1_login = login_user(user1_username, user1_password)
    print(f"用户1登录状态: {user1_login.status_code}")
    
    # 用户2登录
    user2_login = login_user(user2_username, user2_password)
    print(f"用户2登录状态: {user2_login.status_code}")
    
    if user1_login.status_code != 200 or user2_login.status_code != 200:
        print("❌ 登录失败")
        return False
    
    user1_token = user1_login.json()["access_token"]
    user2_token = user2_login.json()["access_token"]
    
    print("\n3. 两个用户分别发送聊天消息...")
    
    # 用户1发送消息
    user1_message = f"用户1的消息 {int(time.time())}"
    user1_chat = send_chat_message(user1_token, user1_message)
    print(f"用户1发送消息状态: {user1_chat.status_code}")
    
    # 用户2发送消息
    user2_message = f"用户2的消息 {int(time.time())}"
    user2_chat = send_chat_message(user2_token, user2_message)
    print(f"用户2发送消息状态: {user2_chat.status_code}")
    
    if user1_chat.status_code != 200 or user2_chat.status_code != 200:
        print("❌ 发送消息失败")
        return False
    
    print("\n4. 验证每个用户只能看到自己的聊天记录...")
    
    # 用户1获取历史
    user1_history = get_chat_history(user1_token)
    print(f"用户1获取历史状态: {user1_history.status_code}")
    
    # 用户2获取历史
    user2_history = get_chat_history(user2_token)
    print(f"用户2获取历史状态: {user2_history.status_code}")
    
    if user1_history.status_code != 200 or user2_history.status_code != 200:
        print("❌ 获取历史失败")
        return False
    
    user1_messages = user1_history.json()
    user2_messages = user2_history.json()
    
    print(f"\n用户1的聊天记录数: {len(user1_messages)}")
    for msg in user1_messages:
        print(f"  - 用户输入: {msg['user_input']}")
        print(f"    AI回复: {msg['ai_reply']}")
    
    print(f"\n用户2的聊天记录数: {len(user2_messages)}")
    for msg in user2_messages:
        print(f"  - 用户输入: {msg['user_input']}")
        print(f"    AI回复: {msg['ai_reply']}")
    
    # 验证每个用户只能看到自己的消息
    user1_has_own_message = any(user1_message in msg['user_input'] for msg in user1_messages)
    user1_has_other_message = any(user2_message in msg['user_input'] for msg in user1_messages)
    user2_has_own_message = any(user2_message in msg['user_input'] for msg in user2_messages)
    user2_has_other_message = any(user1_message in msg['user_input'] for msg in user2_messages)
    
    print(f"\n验证结果:")
    print(f"用户1能看到自己的消息: {'✅' if user1_has_own_message else '❌'}")
    print(f"用户1看不到用户2的消息: {'✅' if not user1_has_other_message else '❌'}")
    print(f"用户2能看到自己的消息: {'✅' if user2_has_own_message else '❌'}")
    print(f"用户2看不到用户1的消息: {'✅' if not user2_has_other_message else '❌'}")
    
    if all([user1_has_own_message, not user1_has_other_message, user2_has_own_message, not user2_has_other_message]):
        print("\n✅ 所有验证通过！聊天系统已成功优化。")
        return True
    else:
        print("\n❌ 部分验证失败。")
        return False

if __name__ == "__main__":
    test_optimization()
    print("\n===== 测试完成 ====")