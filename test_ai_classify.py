#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json

# 测试AI自动分类接口

def test_ai_classify():
    # API端点
    url = "http://127.0.0.1:8000/ai-classify"
    
    # 测试用例
    test_cases = [
        "我忘记密码了，怎么重置？",
        "我的订单什么时候发货？",
        "这个产品有什么功能？",
        "我想退货，怎么操作？",
        "今天天气怎么样？"
    ]
    
    print("开始测试AI自动分类接口...")
    print("=" * 50)
    
    for i, test_input in enumerate(test_cases, 1):
        # 构造请求体
        payload = {
            "user_input": test_input
        }
        
        try:
            # 发送请求
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            print(f"测试用例 {i}: {test_input}")
            print(f"分类结果: {result['category']}")
            print(f"状态码: {response.status_code}")
            print("-" * 50)
            
        except requests.exceptions.RequestException as e:
            print(f"测试用例 {i}: {test_input}")
            print(f"错误: {e}")
            print("-" * 50)

if __name__ == "__main__":
    test_ai_classify()