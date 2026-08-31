"""
聊天 + AI 分类 路由：/ai-classify、/chat
- /ai-classify 路径与响应结构保持不变
- /chat 升级为事件化 SSE（event: category/rag/citation/tool_start/tool_result/message/error/done）
- P3.1 起：路由决策与编排统一收敛到 services/agent/router（prepare_agent_plan），
  本文件只做 API 层：鉴权、会话校验、调用 service、组装 StreamingResponse
"""
import logging

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.category import AIClassifyRequest, AIClassifyResponse
from app.schemas.chat import ChatRequest
from app.services.agent.router import prepare_agent_plan
from app.services.chat_service import chat_event_stream, verify_conversation
from app.services.classification import ai_classify

logger = logging.getLogger("api.chat")

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
        logger.exception("ai-classify top-level error: %s", e)
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

        # 1. Agent 编排（P3.1）：路由决策（normal_chat/rag/order_query/logistics_query/
        #    human_service）+ RAG 检索 + LLM 上下文组装，全部收敛在 service 层
        plan = prepare_agent_plan(
            db, chat_request.conversation_id, chat_request.user_input, chat_request.category
        )

        # 2. 事件化 SSE 流式输出（tool 执行发生在流内：tool_start → tool_result → message）
        return StreamingResponse(
            chat_event_stream(
                user_id=current_user.id,
                conversation_id=chat_request.conversation_id,
                user_input=chat_request.user_input,
                category=plan.category,
                llm_messages=plan.llm_messages,
                rag_result=plan.rag_result,
                route=plan.route,
                tool_call=(
                    {"name": plan.tool_name, "args": plan.tool_args}
                    if plan.tool_name
                    else None
                ),
            ),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # nginx 场景关闭缓冲
            },
        )
    except Exception as e:
        # P4.1：详细错误只进日志，前端不收内部异常细节（SSE 内错误仍走 error 事件协议）
        logger.exception("chat error: %s: %s", type(e).__name__, e)
        return Response(content="服务器错误，请稍后重试", status_code=500)
