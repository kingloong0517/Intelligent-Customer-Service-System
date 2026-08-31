import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey

from app.db.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    message = Column(String, index=True)
    response = Column(String)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    category = Column(String, nullable=True, index=True)
    rag_used = Column(Boolean, nullable=True, default=False)  # P2.2：本次回答是否命中 RAG
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
