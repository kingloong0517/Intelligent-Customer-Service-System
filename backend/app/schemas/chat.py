import datetime
from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_input: str
    conversation_id: int
    category: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str


class Message(BaseModel):
    id: int
    message: str
    response: str
    created_at: datetime.datetime
    category: Optional[str] = None

    class Config:
        orm_mode = True


class ChatHistory(BaseModel):
    id: int
    user_input: str
    ai_reply: str
    timestamp: datetime.datetime
    conversation_id: int
    category: Optional[str] = None
    rag_used: Optional[bool] = None

    class Config:
        orm_mode = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            user_input=obj.message,
            ai_reply=obj.response,
            timestamp=obj.created_at,
            conversation_id=obj.conversation_id,
            category=obj.category,
            rag_used=bool(getattr(obj, "rag_used", False) or False),
        )
