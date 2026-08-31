"""知识库 Pydantic 模型（P2.1）"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------- 知识库 ----------
class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")


class KBInfo(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    document_count: int = 0
    ready_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ---------- 文档 ----------
class DocumentInfo(BaseModel):
    id: int
    kb_id: int
    filename: str
    file_type: str
    size: int
    status: str
    error_message: Optional[str] = None
    chunk_count: int = 0
    embedding_model: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class KBDetail(KBInfo):
    documents: List[DocumentInfo] = []


class DocumentChunkInfo(BaseModel):
    id: int
    chunk_index: int
    content: str
    char_count: int

    class Config:
        orm_mode = True


# ---------- 检索调试（P2.2 RAG 的基础接口） ----------
class KBSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索问题")
    top_k: int = Field(5, ge=1, le=20, description="返回条数")


class KBSearchHit(BaseModel):
    content: str
    score: float
    filename: str
    chunk_index: int


class KBSearchResponse(BaseModel):
    query: str
    embedding_model: str
    hits: List[KBSearchHit] = []
