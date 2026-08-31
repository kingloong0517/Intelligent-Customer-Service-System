"""统一 Agent Router（P3.1）

- route_message：五路由决策（纯规则，第一版；未来可替换为 LLM/Agent 决策）；
- prepare_agent_plan：一次 /chat 的编排（RAG 检索 / Tool 参数 / LLM 上下文组装），
  API 层（api/chat.py）只调用本函数，不感知业务细节。

路由优先级（从前到后）：
  1. 闲聊/寒暄            → normal_chat
  2. 人工客服诉求          → human_service
  3. 物流查询意图          → logistics_query（先于订单：含「到哪/配送」等物流信号）
  4. 订单查询意图          → order_query（提取订单号）
  5. 知识类问题            → rag（复用 rag_service.should_use_rag，原有能力不变）
  6. 兜底                  → normal_chat

约束：
- 不重写 RAG 检索（retrieve_for_chat 原样复用）；
- Embedding / VectorStore / LLM Service 均不修改；
- Tool 只返回结构化数据，自然语言回答由 LLM 生成（chat_service 编排）。
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.chat_service import build_chat_context
from app.services.rag.rag_service import (
    RAGResult,
    build_rag_system_prompt,
    retrieve_for_chat,
    should_use_rag,
)

# 路由常量（与 Tool 名称保持一致，SSE 与落库均使用这些值）

logger = logging.getLogger("agent.router")
ROUTE_NORMAL = "normal_chat"
ROUTE_RAG = "rag"
ROUTE_ORDER = "order_query"
ROUTE_LOGISTICS = "logistics_query"
ROUTE_HUMAN = "human_service"

# 闲聊/寒暄特征（与 rag_service._CHITCHAT_PATTERNS 保持一致语义，前置短路）
_CHITCHAT_PATTERNS = (
    "你好", "您好", "hi", "hello", "在吗", "谢谢", "感谢", "再见", "拜拜",
    "你是谁", "讲个笑话", "笑话", "聊天", "无聊", "早上好", "晚上好", "中午好",
)

# 人工客服诉求
_HUMAN_PATTERNS = ("人工", "转人工", "真人", "投诉", "客服电话")

# 物流查询意图（先于订单判断：物流信号更具体）
# 注意：不放「在哪」——它是日常位置问句高频词（如"发票在哪开"），会误捕知识问题；
# 物流问句几乎必含「快递/物流/包裹/到哪」等强信号词，泛化位置词交给 RAG 兜底
_LOGISTICS_PATTERNS = (
    "快递", "物流", "配送", "包裹", "到哪", "运输", "派送", "收货", "发货进度",
)

# 订单查询意图
_ORDER_PATTERNS = ("订单", "下单", "订单号", "购买记录")

# 订单号提取：消息中出现的 4 位及以上连续数字
_ORDER_ID_RE = re.compile(r"\d{4,}")


@dataclass
class RouteDecision:
    """路由决策结论"""
    route: str
    reason: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    # P3.1 修复：category=其他问题且未命中关键词时的路由盲区探测。
    # True 表示先用真实 Embedding+VectorStore 检索取 score，
    # 由 prepare_agent_plan 按 RAG_SIMILARITY_THRESHOLD 决定最终 rag / normal_chat。
    rag_probe: bool = False


@dataclass
class AgentPlan:
    """一次 /chat 的完整执行计划（API 层只透传给 chat_event_stream）"""
    route: str = ROUTE_NORMAL
    reason: str = ""
    category: str = "其他问题"
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    rag_result: Optional[RAGResult] = None
    rag_system: Optional[str] = None
    llm_messages: List[Dict[str, str]] = field(default_factory=list)


def _extract_order_id(msg: str) -> Optional[str]:
    m = _ORDER_ID_RE.search(msg)
    return m.group(0) if m else None


def route_message(category: Optional[str], user_message: str) -> RouteDecision:
    """五路由决策（规则版）。category 为分类结果（可为空），message 为用户原始输入。"""
    msg = (user_message or "").strip().lower()
    if not msg:
        return RouteDecision(ROUTE_NORMAL, "empty")

    # 1. 人工客服诉求 → 转接提示（P5.1 P1-3：先于闲聊判断，
    #    避免"你好，转人工"被"你好"命中而误判为 normal_chat）
    if any(p in msg for p in _HUMAN_PATTERNS):
        return RouteDecision(ROUTE_HUMAN, "human_request")

    # 2. 闲聊/寒暄 → 普通聊天（无需知识库与工具）
    if any(p in msg for p in _CHITCHAT_PATTERNS):
        return RouteDecision(ROUTE_NORMAL, "chitchat")

    # 3. 订单查询 → order_query Tool（P3.2 起先于物流检查，原因见下）
    if any(p in msg for p in _ORDER_PATTERNS):
        return RouteDecision(
            ROUTE_ORDER, "order_keywords",
            tool_name=ROUTE_ORDER, tool_args={"order_id": _extract_order_id(msg)},
        )

    # 4. 物流查询 → logistics_query Tool。
    #    P3.2 调整说明：logistics_query 依赖 order_query 返回的 order_id/tracking_no
    #    （数据上游）。一句话同时表达订单+物流意图时（如"查订单10001，发货了告诉我物流"），
    #    必须先查订单，再由 Orchestrator 依据订单状态自动接力物流查询；
    #    纯物流消息（无订单词，如"我的快递到哪里了"）不受影响。
    if any(p in msg for p in _LOGISTICS_PATTERNS):
        return RouteDecision(
            ROUTE_LOGISTICS, "logistics_keywords",
            tool_name=ROUTE_LOGISTICS, tool_args={"order_id": _extract_order_id(msg)},
        )

    # 5. 知识类问题 → rag（复用 should_use_rag 原有能力：分类 + 关键词规则）
    if should_use_rag(category, user_message):
        return RouteDecision(ROUTE_RAG, "kb_category_or_keywords")

    # 6. P3.1 修复路由盲区：不再因缺少「退货/退款」等关键词直接放弃。
    #    自然语言表达的知识问题（如「把钱退回来」）允许进入 RAG 检索试探，
    #    由真实 similarity score 决定最终路由（见 prepare_agent_plan）。
    return RouteDecision(ROUTE_NORMAL, "score_probe", rag_probe=True)


def prepare_agent_plan(
    db: Session,
    conversation_id: int,
    user_input: str,
    category: Optional[str],
) -> AgentPlan:
    """编排一次 /chat：路由决策 + RAG 检索 + LLM 上下文组装。

    - API 层只调用本函数与 chat_event_stream，不感知 Agent 业务逻辑；
    - rag 路由复用 retrieve_for_chat / build_rag_system_prompt，检索逻辑零重写；
    - tool 路由只准备名称与参数，Tool 执行发生在 SSE 流内（tool_start → 执行 → tool_result）。
    """
    cat = category or "其他问题"
    decision = route_message(cat, user_input)
    plan = AgentPlan(
        route=decision.route,
        reason=decision.reason,
        category=cat,
        tool_name=decision.tool_name,
        tool_args=decision.tool_args,
    )

    if decision.route == ROUTE_RAG:
        plan.rag_result = retrieve_for_chat(db, user_input)
        if plan.rag_result.used:
            plan.rag_system = build_rag_system_prompt(cat, plan.rag_result.hits)
        logger.info(
            "route=%s reason=%s used=%s top_score=%.4f",
            ROUTE_RAG, plan.rag_result.reason, plan.rag_result.used, plan.rag_result.top_score
        )
    elif decision.rag_probe:
        # P3.1 路由盲区修复：用真实检索分数决定最终路由（threshold 判定在 retrieve_for_chat 内，
        # 未修改 RAG_SIMILARITY_THRESHOLD，不重写检索）。
        plan.rag_result = retrieve_for_chat(db, user_input)
        if plan.rag_result.used:
            # score >= RAG_SIMILARITY_THRESHOLD：真实命中 → 进入 rag
            plan.route = ROUTE_RAG
            plan.reason = "rag_score_hit"
            plan.rag_system = build_rag_system_prompt(cat, plan.rag_result.hits)
        else:
            # score < threshold：维持 normal_chat；rag 事件仍下发（used=false），
            # 与 P2.2「无论是否命中都下发 rag 事件」的协议一致
            plan.reason = "rag_score_low"
        logger.info(
            "route=%s reason=%s top_score=%.4f",
            plan.route, plan.reason, plan.rag_result.top_score
        )
    else:
        logger.info("route=%s reason=%s", decision.route, decision.reason)

    plan.llm_messages = build_chat_context(
        db, conversation_id, user_input, cat, plan.rag_system
    )
    return plan
