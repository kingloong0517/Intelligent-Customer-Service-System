import requests

# 测试 /history 接口
def test_history_api():
    try:
        url = "http://localhost:8000/history"
        response = requests.get(url)
        
        if response.status_code == 200:
            print("✅ /history 接口调用成功！")
            print("返回的数据格式：")
            data = response.json()
            if data:
                # 打印第一条记录的格式
                print(data[0])
            else:
                print("暂无聊天记录")
        else:
            print(f"❌ /history 接口调用失败，状态码：{response.status_code}")
            print(f"错误信息：{response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败：{str(e)}")
        print("请确保后端服务已经启动")

if __name__ == "__main__":
    test_history_api()