"""
聊天业务逻辑：按分类选回复模板 + 哈希选词 + LLM 流式生成（事件化 SSE）
模板回复（pick_reply / sse_generate）保留作为 LLM 不可用时的降级方案。
"""
import asyncio
import datetime
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.conversation import Conversation
from app.models.message import ChatMessage
from app.services.llm import LLMError
from app.services.llm import stream_chat as _llm_stream_chat
from app.services.rag.rag_service import RAGResult, citation_payload
from app.services.agent.orchestrator import ToolOrchestrator
from app.services.tools.registry import build_tool_history_system_prompt, execute_tool

logger = logging.getLogger("app.chat")

# 人工客服转接提示（P3.1：暂不接真实客服系统，固定文案 + 打字机输出）
HUMAN_SERVICE_REPLY = (
    "您好，已为您转接人工客服，请稍候。\n\n"
    "- 人工服务时间：每天 9:00 - 21:00\n"
    "- 请保持页面开启，客服将尽快与您对话。\n\n"
    "如需加快处理，您可以补充订单号或问题描述。"
)


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
    rag_used: bool = False,
) -> Tuple[ChatMessage, Conversation]:
    chat_message = ChatMessage(
        user_id=user_id,
        conversation_id=conversation_id,
        message=user_input,
        response=reply,
        category=category,
        rag_used=rag_used,
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
    """SSE 逐字生成器（旧协议，保留用于兼容参考，新链路不再使用）"""
    for char in reply:
        yield f"data: {char}\n\n"
        await asyncio.sleep(0.1)
    yield "data: [DONE]\n\n"


# =====================================================================
# 事件化 SSE（P1）：协议为 `event: <type>\ndata: <json>\n\n`
# 事件类型：category / message / error / done（预留：rag / citation /
# tool_start / tool_result，前端 onEvent 结构已就位，后端按需扩展）
# =====================================================================

LLM_HISTORY_LIMIT = 10  # 送入 LLM 的历史消息轮数上限


def sse_event(event: str, payload: dict) -> str:
    """格式化一条 SSE 事件；JSON 内换行被转义，不会破坏 data 行结构"""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def build_system_prompt(category: str) -> str:
    base = "你是企业级智能客服助手，请用中文、专业、简洁地回答用户问题，适当使用 Markdown 格式。"
    if category and category != "其他问题":
        base += (
            f"当前用户问题已被分类为「{category}」，请围绕该类别作答；"
            "如涉及订单、物流、退款等需要查询的业务信息，请礼貌引导用户提供订单号。"
        )
    return base


def build_chat_context(
    db: Session,
    conversation_id: int,
    user_input: str,
    category: str,
    rag_system: str = None,
) -> List[Dict[str, str]]:
    """组装 LLM 上下文：system(含分类/RAG context) + 最近历史 + 当前输入（当前消息尚未落库）"""
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(LLM_HISTORY_LIMIT)
        .all()
    )
    history.reverse()

    system_content = rag_system if rag_system else build_system_prompt(category)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content}
    ]
    for m in history:
        if m.message:
            messages.append({"role": "user", "content": m.message})
        if m.response:
            messages.append({"role": "assistant", "content": m.response})
    messages.append({"role": "user", "content": user_input})
    return messages


def _persist_chat(
    user_id: int,
    conversation_id: int,
    user_input: str,
    reply: str,
    category: str,
    rag_used: bool = False,
) -> int:
    """用独立 Session 落库（不依赖请求生命周期，流式结束/断开时均可安全调用）"""
    db = SessionLocal()
    try:
        msg, _conv = save_chat(db, user_id, conversation_id, user_input, reply, category, rag_used)
        return msg.id
    finally:
        db.close()


async def _template_reply_stream(reply: str) -> AsyncGenerator[str, None]:
    """模板降级输出：小片推送 + 轻微延迟，保持打字机体验"""
    for i in range(0, len(reply), 2):
        yield reply[i : i + 2]
        await asyncio.sleep(0.04)


async def chat_event_stream(
    user_id: int,
    conversation_id: int,
    user_input: str,
    category: str,
    llm_messages: List[Dict[str, str]],
    rag_result: RAGResult = None,
    route: str = "normal_chat",
    tool_call: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """
    /chat 事件流主流程（P3.1 Agent Router 接入后）：
      category 事件
      → [rag / citation 事件（rag 路由时）]
      → [tool_start / tool_result 事件（tool 路由时，结果注入 LLM 上下文）]
      → LLM 流式 message 事件（human_service 为固定文案，不调 LLM）
      （失败降级模板）→ 落库 → done 事件。
    - rag 事件始终携带 used/reason，记录本次是否命中 RAG；
    - citation 仅在真实检索命中时发送，全部来自检索结果，不伪造；
    - tool_result 携带结构化数据，自然语言回答由 LLM 基于结果生成；
    - 无 Key / 首包前失败 → 完整降级为模板回复；
    - 流中途失败 → 发 error 事件，已生成内容仍落库；
    - 客户端断开（GeneratorExit）→ finally 中保存已生成内容，保证历史完整；
    - done 始终作为流的最后一个事件（message_id 在落库后回填）。
    """
    full_reply = ""
    message_id = None
    rag_used = bool(rag_result and rag_result.used)
    try:
        # 分类结果 + 路由结论下发（intent 暂与 category 相同，route 为 P3.1 Agent 路由）
        yield sse_event(
            "category", {"category": category, "intent": category, "route": route}
        )

        # RAG 路由与检索结论（P2.2）：无论是否命中都下发 rag 事件
        if rag_result is not None:
            yield sse_event("rag", rag_result.to_event())
            if rag_result.used:
                # citation 在 message 流之前发送，不破坏 token 流
                for hit in rag_result.hits:
                    yield sse_event("citation", citation_payload(hit))

        # Tool 编排（P3.2）：Orchestrator 决定链式调用顺序，逐步下发 tool_start/tool_result；
        # 每步失败或达到 MAX_TOOL_STEPS 即停止继续调用，已有结果仍交给 LLM 回答
        if tool_call:
            orch = ToolOrchestrator(
                route=route,
                first_tool=tool_call.get("name"),
                first_args=tool_call.get("args") or {},
            )
            while True:
                step = orch.next_step()
                if step is None:
                    break
                logger.info("tool_start tool=%s arguments=%s", step.tool, step.arguments)
                yield sse_event(
                    "tool_start", {"tool": step.tool, "arguments": step.arguments}
                )
                _t_tool = time.perf_counter()
                step_result = execute_tool(step.tool, step.arguments)
                logger.info(
                    "tool_result tool=%s ok=%s duration_ms=%d",
                    step.tool, bool(step_result.get("ok")),
                    int((time.perf_counter() - _t_tool) * 1000),
                )
                yield sse_event(
                    "tool_result",
                    {
                        "tool": step.tool,
                        "ok": bool(step_result.get("ok")),
                        "result": step_result,
                    },
                )
                orch.record(step.tool, step.arguments, step_result)
            if orch.limit_hit:
                logger.warning(
                    "tool chain stopped: max_tool_steps=%d reached", orch.max_steps
                )
            if orch.history:
                llm_messages = list(llm_messages or []) + [
                    {"role": "system", "content": build_tool_history_system_prompt(orch.history)}
                ]

        if route == "human_service":
            # 转接提示：固定文案，不调 LLM（复用打字机输出，保持一致体验）
            async for chunk in _template_reply_stream(HUMAN_SERVICE_REPLY):
                full_reply += chunk
                yield sse_event("message", {"content": chunk})
        else:
            llm_started = False
            try:
                async for delta in _llm_stream_chat(llm_messages):
                    llm_started = True
                    full_reply += delta
                    yield sse_event("message", {"content": delta})
            except LLMError as e:
                if llm_started:
                    # 已输出部分内容后再失败：告知前端中断，不再补模板拼接
                    logger.error("llm stream interrupted: %s", e)
                    yield sse_event(
                        "error",
                        {"code": "llm_interrupted", "message": "AI 回复中断，请稍后重试"},
                    )
                else:
                    # 首包前失败（无 Key / 网络 / 鉴权 / 402）：完整降级为模板回复
                    logger.warning(
                        "llm unavailable, fallback to template: %s status_code=%s",
                        e, getattr(e, "status_code", None),
                    )
                    template = pick_reply(user_input, category)
                    async for chunk in _template_reply_stream(template):
                        full_reply += chunk
                        yield sse_event("message", {"content": chunk})

        _t_persist = time.perf_counter()
        try:
            message_id = _persist_chat(
                user_id, conversation_id, user_input, full_reply, category, rag_used
            )
            logger.info(
                "chat_persist=success message_id=%s duration_ms=%d",
                message_id, int((time.perf_counter() - _t_persist) * 1000),
            )
        except Exception as e:
            # P5.1 P1-6：落库失败不阻塞 done 事件，保证客户端能正常结束 loading
            logger.error("chat_persist=failed error=%s", e)
            message_id = None
        yield sse_event(
            "done",
            {"message_id": message_id, "conversation_id": conversation_id},
        )
    finally:
        # 断开 / 落库前异常的兜底：只要生成过内容且尚未落库，就保存
        if message_id is None and full_reply:
            try:
                _persist_chat(
                    user_id, conversation_id, user_input, full_reply, category, rag_used
                )
            except Exception as e:
                logger.error("fallback persist on disconnect failed: %s", e)
