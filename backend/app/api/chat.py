"""
聊天 + AI 分类 路由：/ai-classify、/chat
路径、请求方式、响应结构与原 main.py 623-817 完全一致
"""
import traceback

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.category import AIClassifyRequest, AIClassifyResponse
from app.schemas.chat import ChatRequest
from app.services.chat_service import (
    pick_reply,
    save_chat,
    sse_generate,
    verify_conversation,
)
from app.services.classification import ai_classify

router = APIRouter()


@router.post("/ai-classify", response_model=AIClassifyResponse)
def ai_classify_api(
    request: AIClassifyRequest,
    db: Session = Depends(get_db),
):
    """注意：原代码 /ai-classify 未强制加 Depends(get_current_user)，保持不变"""
    try:
        category = ai_classify(db, request.user_input)
        return AIClassifyResponse(category=category)
    except Exception as e:
        print(f"[api/chat] 分类错误（顶层兜底）: {str(e)}")
        return AIClassifyResponse(category="其他问题")


@router.post("/chat")
def chat(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        conversation = verify_conversation(
            db, chat_request.conversation_id, current_user.id
        )
        if not conversation:
            return Response(content="会话不存在", status_code=404)

        # 1. 选回复模板
        reply = pick_reply(chat_request.user_input, chat_request.category)

        # 2. 保存聊天记录 + 更新会话（先落库）
        save_chat(
            db,
            user_id=current_user.id,
            conversation_id=chat_request.conversation_id,
            user_input=chat_request.user_input,
            reply=reply,
            category=chat_request.category or "其他问题",
        )

        # 3. 返回 SSE 流式输出
        return StreamingResponse(
            sse_generate(reply), media_type="text/event-stream"
        )
    except Exception as e:
        print(f"[api/chat] 聊天错误: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        return Response(content=f"服务器错误: {str(e)}", status_code=500)
