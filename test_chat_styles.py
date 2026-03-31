import requests
import json
import time

# 登录获取token
def login():
    url = "http://localhost:8000/login"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"username": "testuser", "password": "testpassword"}
    
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"登录失败: {response.text}")
            return None
    except Exception as e:
        print(f"登录异常: {str(e)}")
        return None

# 发送聊天消息并获取响应
def send_chat_message(token, conversation_id, user_input, category):
    url = "http://localhost:8000/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "conversation_id": conversation_id,
        "user_input": user_input,
        "category": category
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), stream=True)
        if response.status_code == 200:
            ai_response = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        ai_response += line[6:]
            return ai_response
        else:
            return f"请求失败: {response.text}"
    except Exception as e:
        return f"请求异常: {str(e)}"

# 获取会话列表
def get_conversations(token):
    url = "http://localhost:8000/conversations"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取会话失败: {response.text}")
            return []
    except Exception as e:
        print(f"获取会话异常: {str(e)}")
        return []

# 创建新会话
def create_conversation(token):
    url = "http://localhost:8000/conversations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "title": "测试会话"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            return response.json()["id"]
        else:
            print(f"创建会话失败: {response.text}")
            return None
    except Exception as e:
        print(f"创建会话异常: {str(e)}")
        return None

# 测试不同分类的问题
def test_chat_styles():
    # 登录获取token
    token = login()
    if not token:
        return
    
    # 获取会话或创建新会话
    conversations = get_conversations(token)
    if conversations:
        conversation_id = conversations[0]["id"]
        print(f"使用现有会话: {conversation_id}")
    else:
        conversation_id = create_conversation(token)
        if not conversation_id:
            return
        print(f"创建新会话: {conversation_id}")
    
    # 测试不同分类的问题
    test_cases = [
        ("账户问题", "我忘记了密码，怎么重置？"),
        ("订单咨询", "我的订单什么时候发货？"),
        ("产品咨询", "这个产品有什么功能？"),
        ("售后问题", "我收到的商品有问题，怎么退换？"),
        ("其他问题", "今天天气怎么样？")
    ]
    
    for category, user_input in test_cases:
        print(f"\n=== 测试分类: {category} ===")
        print(f"用户输入: {user_input}")
        ai_response = send_chat_message(token, conversation_id, user_input, category)
        print(f"AI回答: {ai_response}")
        time.sleep(1)  # 休息1秒，避免请求过于频繁

if __name__ == "__main__":
    test_chat_styles()
