"""
会话 & 聊天记录 相关业务逻辑
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import ChatMessage
from app.schemas.chat import ChatHistory, Message
from app.schemas.conversation import ConversationCreate


VALID_STATUSES = ["active", "ended", "archived"]


# ---------- 会话 ----------
def list_conversations(db: Session, user_id: int) -> List[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def create_conversation(
    db: Session, user_id: int, payload: ConversationCreate
) -> Conversation:
    db_conv = Conversation(
        user_id=user_id,
        title=payload.title,
        status=payload.status or "active",
    )
    db.add(db_conv)
    db.commit()
    db.refresh(db_conv)
    return db_conv


def get_conversation_of_user(
    db: Session, conversation_id: int, user_id: int
) -> Optional[Conversation]:
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .first()
    )


def delete_conversation_cascade(db: Session, conversation_id: int, user_id: int) -> bool:
    conv = get_conversation_of_user(db, conversation_id, user_id)
    if not conv:
        return False
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()
    return True


def update_conversation_status(
    db: Session, conversation_id: int, user_id: int, status: str
) -> Tuple[Optional[Conversation], Optional[str]]:
    """返回 (updated_conversation, error_msg)"""
    if not status or status not in VALID_STATUSES:
        return None, f"无效的状态值，必须是 {', '.join(VALID_STATUSES)} 中的一个"
    conv = get_conversation_of_user(db, conversation_id, user_id)
    if not conv:
        return None, "会话不存在"
    conv.status = status
    db.commit()
    db.refresh(conv)
    return conv, None


# ---------- 聊天记录 ----------
def list_messages(
    db: Session,
    user_id: int,
    conversation_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[Optional[str], List[Message]]:
    query = db.query(ChatMessage).filter(ChatMessage.user_id == user_id)
    if conversation_id:
        if not get_conversation_of_user(db, conversation_id, user_id):
            return "会话不存在", []
        query = query.filter(ChatMessage.conversation_id == conversation_id)
    # P5.1 P1-5：返回最新 N 条（desc + limit 后 reverse 恢复时间正序），
    # 避免超过 limit 条消息时用户看不到最新消息
    rows = query.order_by(ChatMessage.created_at.desc()).offset(skip).limit(limit).all()
    rows.reverse()
    return None, rows


def list_history(
    db: Session,
    user_id: int,
    conversation_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[Optional[str], List[ChatHistory]]:
    query = db.query(ChatMessage).filter(ChatMessage.user_id == user_id)
    if conversation_id:
        if not get_conversation_of_user(db, conversation_id, user_id):
            return "会话不存在", []
        query = query.filter(ChatMessage.conversation_id == conversation_id)
    # P5.1 P1-5：返回最新 N 条（desc + limit 后 reverse 恢复时间正序）
    rows = query.order_by(ChatMessage.created_at.desc()).offset(skip).limit(limit).all()
    rows.reverse()
    return None, [ChatHistory.from_orm(m) for m in rows]
