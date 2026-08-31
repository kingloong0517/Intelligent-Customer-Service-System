"""RAG Service（P2.2）：将知识库检索接入 /chat

- should_use_rag：独立路由判断层（未来 Agent 直接替换此函数即可，调用方不感知）；
- retrieve_for_chat：跨全部知识库检索 Top-K + 相似度阈值过滤；
- build_rag_system_prompt：RAG 模式 system prompt（含 Top-K context，禁止编造）。

复用 P2.1 的 get_embedder / get_vector_store，不重新实现向量检索。
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import RAG_SIMILARITY_THRESHOLD, RAG_SNIPPET_MAX_LEN, RAG_TOP_K
from app.models.kb import KnowledgeBase
from app.services.rag.embedder import EmbeddingError, get_embedder
from app.services.rag.vector_store import get_vector_store

logger = logging.getLogger("rag_service")

# 需要知识库支撑的客服知识类分类（与 init_db 默认分类对齐）
_KB_CATEGORIES = {"产品咨询", "售后问题", "账户问题", "订单咨询"}

# 明显闲聊/寒暄特征：命中即跳过 RAG（无需知识库）
_CHITCHAT_PATTERNS = (
    "你好", "您好", "hi", "hello", "在吗", "谢谢", "感谢", "再见", "拜拜",
    "你是谁", "讲个笑话", "笑话", "聊天", "无聊", "早上好", "晚上好", "中午好",
)

# 无明确分类时，命中这些客服知识类关键词也进入 RAG
_KB_KEYWORDS = (
    "退货", "退款", "换货", "保修", "维修", "发票", "订单", "物流", "发货",
    "快递", "政策", "条款", "密码", "账号", "账户", "登录", "注册", "充值",
    "会员", "优惠券", "产品", "功能", "说明书", "手册", "使用方法", "怎么安装",
    "如何使用", "faq", "FAQ",
)


@dataclass
class RAGResult:
    """一次 /chat 请求的 RAG 路由与检索结论"""
    used: bool = False
    reason: str = "disabled"          # disabled / chitchat / no_kb / low_similarity / error / ok
    top_score: float = 0.0
    embedding_model: str = ""
    hits: List[Dict] = field(default_factory=list)

    def to_event(self) -> Dict:
        """SSE rag 事件载荷（used=false 时不携带 hits，避免误导）"""
        return {
            "used": self.used,
            "reason": self.reason,
            "top_score": round(self.top_score, 4) if self.top_score else 0.0,
            "embedding_model": self.embedding_model,
            "chunk_count": len(self.hits),
        }


def should_use_rag(category: Optional[str], user_message: str) -> bool:
    """
    RAG 路由判断（第一版：分类 + 关键词规则；未来 Agent 替换此层）：
    - 明显闲聊/寒暄 → False；
    - 命中客服知识类分类（产品咨询/售后问题/账户问题/订单咨询）→ True；
    - 其他问题：消息中出现客服知识关键词 → True，否则 False。
    """
    msg = (user_message or "").strip().lower()
    if not msg:
        return False
    if any(p in msg for p in _CHITCHAT_PATTERNS):
        return False
    if category and category in _KB_CATEGORIES:
        return True
    return any(k in msg for k in _KB_KEYWORDS)


def retrieve_for_chat(db: Session, query: str) -> RAGResult:
    """
    对全部知识库做向量检索（企业知识统一检索），返回 RAGResult：
    - 无知识库/无数据 → reason=no_kb；
    - 最高分低于阈值 → reason=low_similarity（不强行使用无关内容）；
    - Embedding 异常 → reason=error（不阻塞聊天，上层继续走普通 LLM）。
    """
    result = RAGResult()
    embedder = get_embedder()
    result.embedding_model = embedder.name
    _t0 = time.perf_counter()

    kb_ids = [kb.id for kb in db.query(KnowledgeBase).all()]
    if not kb_ids:
        result.reason = "no_kb"
        logger.info(
            "rag retrieve used=%s reason=%s top_k=%d hit_count=0 embedding_model=%s duration_ms=%d",
            result.used, result.reason, RAG_TOP_K, result.embedding_model,
            int((time.perf_counter() - _t0) * 1000),
        )
        return result

    try:
        query_vector = embedder.embed([query])[0]
    except EmbeddingError as e:
        logger.warning("RAG embedding 失败，跳过检索: %s", e)
        result.reason = "error"
        logger.info(
            "rag retrieve used=%s reason=%s top_k=%d hit_count=0 embedding_model=%s duration_ms=%d",
            result.used, result.reason, RAG_TOP_K, result.embedding_model,
            int((time.perf_counter() - _t0) * 1000),
        )
        return result

    store = get_vector_store()
    merged: List[Dict] = []
    for kb_id in kb_ids:
        # P5.1 P1-1：单个知识库向量查询失败时不中断整体检索，跳过该库并记录 warning
        try:
            for hit in store.query(f"kb_{kb_id}", query_vector, RAG_TOP_K):
                hit["kb_id"] = kb_id
                merged.append(hit)
        except Exception as e:
            logger.warning("vector store query failed for kb_%s: %s", kb_id, e)
            continue
    if not merged:
        result.reason = "no_kb"
        logger.info(
            "rag retrieve used=%s reason=%s top_k=%d hit_count=0 embedding_model=%s duration_ms=%d",
            result.used, result.reason, RAG_TOP_K, result.embedding_model,
            int((time.perf_counter() - _t0) * 1000),
        )
        return result

    merged.sort(key=lambda h: h["score"], reverse=True)
    result.top_score = merged[0]["score"]

    if result.top_score < RAG_SIMILARITY_THRESHOLD:
        result.reason = "low_similarity"
        logger.info(
            "rag retrieve used=%s reason=%s top_score=%.4f top_k=%d hit_count=0 embedding_model=%s duration_ms=%d",
            result.used, result.reason, result.top_score, RAG_TOP_K, result.embedding_model,
            int((time.perf_counter() - _t0) * 1000),
        )
        return result

    result.hits = [
        {
            "kb_id": h["kb_id"],
            "document_id": h["metadata"].get("document_id"),
            "document_name": h["metadata"].get("filename", ""),
            "chunk_index": h["metadata"].get("chunk_index", 0),
            "chunk_key": h["id"],
            "score": round(h["score"], 4),
            "content": h["document"],
        }
        for h in merged[:RAG_TOP_K]
    ]
    result.used = True
    result.reason = "ok"
    # P4.1 可观测性：只记录指标（score/数量/模型/耗时），绝不记录 chunk 全文
    logger.info(
        "rag retrieve used=%s reason=%s top_score=%.4f top_k=%d hit_count=%d embedding_model=%s duration_ms=%d",
        result.used, result.reason, result.top_score, RAG_TOP_K, len(result.hits),
        result.embedding_model, int((time.perf_counter() - _t0) * 1000),
    )
    return result


def build_rag_system_prompt(category: Optional[str], hits: List[Dict]) -> str:
    """RAG 模式 system prompt：默认客服人设 + 检索 context + 防编造指令"""
    base = "你是企业级智能客服助手，请用中文、专业、简洁、友好地回答用户问题，适当使用 Markdown 格式。"
    if category and category != "其他问题":
        base += f"当前用户问题分类为「{category}」。"
    base += (
        "\n\n回答要求：\n"
        "1. 优先依据下方「知识库参考内容」回答；\n"
        "2. 参考内容中没有的信息，绝对不要编造，应明确告知用户暂时没有找到相关信息，"
        "并建议用户联系人工客服或提供更多细节；\n"
        "3. 引用参考内容时保持自然，不需要输出编号；\n"
        "4. 保持正常客服语气。\n\n"
        "【知识库参考内容】\n"
    )
    for i, h in enumerate(hits, start=1):
        base += f"[{i}] (来源: {h['document_name']}, 片段{h['chunk_index'] + 1})\n{h['content']}\n\n"
    return base


def citation_payload(hit: Dict) -> Dict:
    """SSE citation 事件载荷：全部来自真实检索结果，无任何写死/伪造字段"""
    snippet = hit["content"][:RAG_SNIPPET_MAX_LEN]
    if len(hit["content"]) > RAG_SNIPPET_MAX_LEN:
        snippet += "…"
    return {
        "kb_id": hit["kb_id"],
        "document_id": hit["document_id"],
        "filename": hit["document_name"],
        "chunk_index": hit["chunk_index"],
        "chunk_key": hit["chunk_key"],
        "score": hit["score"],
        "snippet": snippet,
    }
