"""知识库数据模型（P2.1）：knowledge_bases / documents / document_chunks"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class KnowledgeBase(Base):
    """企业客服知识库"""
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    """知识库文档，status: pending / processing / ready / failed"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)          # 原始文件名
    file_path = Column(String(500), nullable=False)         # 服务器存储路径
    file_type = Column(String(10), nullable=False)          # pdf / txt / md
    size = Column(Integer, nullable=False, default=0)       # 字节数
    status = Column(String(20), nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)             # 处理失败原因（不静默失败）
    chunk_count = Column(Integer, nullable=False, default=0)
    embedding_model = Column(String(100), nullable=True)    # 处理时使用的 Embedding 标识
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """文档分块，向量本体存于 VectorStore（以 chunk_key 关联）"""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)           # 文档内序号
    chunk_key = Column(String(100), nullable=False, index=True)  # VectorStore 中的唯一 id
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")
