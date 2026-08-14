import datetime
from typing import Optional

from pydantic import BaseModel


class ConversationBase(BaseModel):
    title: str
    status: Optional[str] = "active"


class ConversationCreate(ConversationBase):
    pass


class ConversationInfo(ConversationBase):
    id: int
    user_id: int
    last_message: Optional[str] = None
    message_count: int = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True
