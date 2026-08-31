"""
会话与聊天记录路由：
/conversations*、/messages、/history
路径、请求方式、响应结构与原 main.py 474-549 + 821-865 完全一致
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.chat import ChatHistory, Message
from app.schemas.conversation import ConversationCreate, ConversationInfo
from app.services.conversation import (
    create_conversation,
    delete_conversation_cascade,
    get_conversation_of_user,
    list_conversations,
    list_history,
    list_messages,
    update_conversation_status,
)

logger = logging.getLogger("api.conversations")

router = APIRouter()


# ========== 会话 ==========
@router.get("/conversations", response_model=List[ConversationInfo])
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return list_conversations(db, current_user.id)
    except Exception as e:
        logger.exception("list conversations failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="获取会话列表失败，请稍后重试")


@router.post("/conversations", response_model=ConversationInfo)
def create_conversation_api(
    conversation: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_conversation(db, current_user.id, conversation)


@router.delete("/conversations/{conversation_id}")
def delete_conversation_api(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = delete_conversation_cascade(db, conversation_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "会话已删除"}


@router.put("/conversations/{conversation_id}/status")
def update_conversation_status_api(
    conversation_id: int,
    status_update: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_status = status_update.get("status")
    conv, err = update_conversation_status(
        db, conversation_id, current_user.id, new_status
    )
    if err:
        if err == "会话不存在":
            raise HTTPException(status_code=404, detail=err)
        raise HTTPException(status_code=400, detail=err)
    return {"message": "会话状态已更新", "conversation": conv}


# ========== 聊天记录 ==========
@router.get("/messages", response_model=List[Message])
def get_messages(
    current_user: User = Depends(get_current_user),
    conversation_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    err, rows = list_messages(db, current_user.id, conversation_id, skip, limit)
    if err:
        raise HTTPException(status_code=404, detail=err)
    return rows


@router.get("/history", response_model=List[ChatHistory])
def get_chat_history(
    current_user: User = Depends(get_current_user),
    conversation_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    err, rows = list_history(db, current_user.id, conversation_id, skip, limit)
    if err:
        raise HTTPException(status_code=404, detail=err)
    return rows
