"""
聊天业务逻辑：按分类选回复模板 + 哈希选词
与原 main.py 729-776 完全一致
"""
import asyncio
import datetime
from typing import Generator, Tuple

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import ChatMessage


CATEGORY_RESPONSES = {
    "账户问题": [
        "关于您的账户问题，我来为您详细解答。",
        "账户相关问题处理需要谨慎，让我帮您确认一下。",
        "对于账户问题，我需要了解一些具体信息才能更好地帮助您。",
        "账户问题通常与登录、注册或个人信息相关，让我为您分析。",
        "您的账户安全是我们的首要考虑，让我为您解决这个问题。",
    ],
    "订单咨询": [
        "关于您的订单，我来为您查询最新状态。",
        "订单相关问题需要确认订单编号等信息，让我帮您处理。",
        "订单查询、修改或取消等问题，我都可以为您提供帮助。",
        "您的订单进展情况如下，让我为您详细说明。",
        "订单咨询请提供订单号，我会尽快为您查询。",
    ],
    "产品咨询": [
        "关于产品信息，我来为您详细介绍。",
        "这款产品的主要特点包括...",
        "产品咨询方面，我可以为您提供规格、功能、使用方法等信息。",
        "针对您的产品问题，让我为您做出专业解答。",
        "产品的使用技巧和注意事项如下...",
    ],
    "售后问题": [
        "对于售后问题，我深表歉意，让我为您解决。",
        "售后问题处理流程包括...让我为您跟进。",
        "您的售后需求我已经记录，将尽快为您处理。",
        "售后问题需要一些信息来确认，让我为您收集。",
        "我们重视每一位客户的售后体验，我会尽力为您解决。",
    ],
    "其他问题": [
        "关于这个问题，我来为您详细解答。",
        "非常感谢您的提问，我很乐意为您提供帮助。",
        "您的问题比较特殊，让我为您分析一下。",
        "对于这类问题，我可以从以下几个方面为您说明。",
        "希望我的回答能够满足您的需求。",
    ],
}


def pick_reply(user_input: str, category: str) -> str:
    current_category = category if category in CATEGORY_RESPONSES else "其他问题"
    responses = CATEGORY_RESPONSES[current_category]
    reply_index = hash(user_input) % len(responses)
    return responses[reply_index]


def verify_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .first()
    )


def save_chat(
    db: Session,
    user_id: int,
    conversation_id: int,
    user_input: str,
    reply: str,
    category: str,
) -> Tuple[ChatMessage, Conversation]:
    chat_message = ChatMessage(
        user_id=user_id,
        conversation_id=conversation_id,
        message=user_input,
        response=reply,
        category=category,
    )
    db.add(chat_message)

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.updated_at = datetime.datetime.utcnow()
        preview = user_input[:50] + ("..." if len(user_input) > 50 else "")
        conversation.last_message = preview
        conversation.message_count = (conversation.message_count or 0) + 1

    db.commit()
    db.refresh(chat_message)
    return chat_message, conversation


async def sse_generate(reply: str) -> Generator[str, None, None]:
    """SSE 逐字生成器，与原 main.py 779-786 完全一致"""
    for char in reply:
        yield f"data: {char}\n\n"
        await asyncio.sleep(0.1)
    yield "data: [DONE]\n\n"
