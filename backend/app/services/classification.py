"""
AI 自动分类：优先调 DeepSeek API，失败则用关键词兜底
与原 main.py 623-712 逻辑完全一致；密钥从 config 读取，不再硬编码
"""
from typing import List

import requests
from sqlalchemy.orm import Session

from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL
from app.models.category import Category


def _build_classify_prompt(user_input: str, category_names: List[str]) -> str:
    return f"""你是一个客服系统的分类助手，请根据用户的问题将其分类为以下类别之一：
{', '.join(category_names)}

请严格按照要求进行分类：
1. 只返回分类结果，不要添加任何解释或说明
2. 必须从给定的分类列表中选择，不能自创分类
3. 如果无法确定分类，返回'其他问题'

用户问题：{user_input}
分类结果："""


def _keyword_fallback(user_input: str) -> str:
    text = user_input.lower()
    if any(k in text for k in ["登录", "注册", "密码", "账户", "账号"]):
        return "账户问题"
    if any(k in text for k in ["订单", "支付", "物流", "发货", "运费"]):
        return "订单咨询"
    if any(k in text for k in ["产品", "功能", "使用", "怎么", "如何"]):
        return "产品咨询"
    if any(k in text for k in ["退货", "换货", "维修", "售后", "退款"]):
        return "售后问题"
    return "其他问题"


def ai_classify(db: Session, user_input: str) -> str:
    categories = db.query(Category).all()
    category_names = [cat.name for cat in categories]

    print(f"[classification] 用户问题: {user_input}")
    print(f"[classification] 可用分类: {category_names}")

    # 如果没有配置密钥，直接走兜底
    if not DEEPSEEK_API_KEY:
        print("[classification] 无 DEEPSEEK_API_KEY，使用关键词兜底")
        return _keyword_fallback(user_input)

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的客服分类助手，只能输出指定的分类名称。"},
                {"role": "user", "content": _build_classify_prompt(user_input, category_names)},
            ],
            "temperature": 0.1,
            "max_tokens": 10,
        }

        print(f"[classification] 调用 DeepSeek API...")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        result = response.json()

        category = result["choices"][0]["message"]["content"].strip()
        print(f"[classification] DeepSeek API返回的分类: {category}")

        if category not in category_names:
            print(f"[classification] 分类'{category}'不在预定义列表中，使用默认分类")
            category = "其他问题"
        else:
            print(f"[classification] 分类'{category}'有效")

        return category

    except requests.RequestException as e:
        print(f"[classification] 调用DeepSeek API错误: {str(e)}，使用关键词兜底")
        return _keyword_fallback(user_input)
    except Exception as e:
        print(f"[classification] 分类错误: {str(e)}，返回默认分类")
        return "其他问题"
