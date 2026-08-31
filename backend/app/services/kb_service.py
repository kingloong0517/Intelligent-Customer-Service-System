"""知识库业务逻辑（P2.1）：KB/文档 CRUD、级联删除、检索调试

复杂业务（解析/chunk/embedding/向量写入）在 kb_processor，本模块不承担。
"""
import logging
import os
import re
import shutil
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import KB_UPLOAD_DIR
from app.models.kb import Document, DocumentChunk, KnowledgeBase
from app.services.rag.embedder import get_embedder
from app.services.rag.vector_store import get_vector_store

logger = logging.getLogger("kb_service")


class KBNotFoundError(Exception):
    pass


class KBDuplicateError(Exception):
    pass


def _collection(kb_id: int) -> str:
    return f"kb_{kb_id}"


# ---------- 知识库 ----------
def create_kb(db: Session, name: str, description: Optional[str]) -> KnowledgeBase:
    if db.query(KnowledgeBase).filter(KnowledgeBase.name == name).first():
        raise KBDuplicateError(f"知识库名称已存在: {name}")
    kb = KnowledgeBase(name=name, description=description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def list_kbs(db: Session) -> List[dict]:
    kbs = db.query(KnowledgeBase).order_by(KnowledgeBase.id).all()
    result = []
    for kb in kbs:
        docs = db.query(Document).filter(Document.kb_id == kb.id).all()
        result.append(
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "document_count": len(docs),
                "ready_count": sum(1 for d in docs if d.status == "ready"),
                "created_at": kb.created_at,
            }
        )
    return result


def get_kb_detail(db: Session, kb_id: int) -> Optional[dict]:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        return None
    docs = db.query(Document).filter(Document.kb_id == kb_id).order_by(Document.id).all()
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "document_count": len(docs),
        "ready_count": sum(1 for d in docs if d.status == "ready"),
        "created_at": kb.created_at,
        "documents": docs,
    }


def delete_kb(db: Session, kb_id: int) -> bool:
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        return False
    # 向量 collection 整体删除
    get_vector_store().delete_collection(_collection(kb_id))
    # 上传目录整体删除（尽力，失败不阻塞）
    kb_dir = os.path.join(KB_UPLOAD_DIR, f"kb{kb_id}")
    try:
        if os.path.isdir(kb_dir):
            shutil.rmtree(kb_dir, ignore_errors=True)
    except Exception as e:
        logger.warning("delete kb upload dir failed: %s", e)
    # DB 级联：chunks/documents 由 relationship cascade 删除
    db.delete(kb)
    db.commit()
    return True


# ---------- 文档 ----------
def _safe_filename(filename: str) -> str:
    base = os.path.basename(filename or "file")
    return re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", base).strip("._") or "file"


def add_document(db: Session, kb_id: int, filename: str, data: bytes) -> Document:
    """保存上传文件并创建 pending 状态的文档记录（处理由后台任务执行）"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise KBNotFoundError(f"知识库不存在: {kb_id}")
    file_type = filename.rsplit(".", 1)[-1].lower()

    doc = Document(
        kb_id=kb_id,
        filename=filename,
        file_path="",  # flush 拿到 id 后回填
        file_type=file_type,
        size=len(data),
        status="pending",
    )
    db.add(doc)
    db.flush()

    kb_dir = os.path.join(KB_UPLOAD_DIR, f"kb{kb_id}")
    os.makedirs(kb_dir, exist_ok=True)
    file_path = os.path.join(kb_dir, f"doc{doc.id}_{_safe_filename(filename)}")
    with open(file_path, "wb") as f:
        f.write(data)

    doc.file_path = file_path
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, kb_id: int, document_id: int) -> Optional[Document]:
    return (
        db.query(Document)
        .filter(Document.kb_id == kb_id, Document.id == document_id)
        .first()
    )


def delete_document(db: Session, kb_id: int, document_id: int) -> bool:
    doc = get_document(db, kb_id, document_id)
    if not doc:
        return False
    # 向量按 document_id 精确删除
    get_vector_store().delete_where(_collection(kb_id), {"document_id": document_id})
    # 物理文件删除（尽力）
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception as e:
        logger.warning("delete document file failed: %s", e)
    # DB 级联：chunks 由 cascade 删除
    db.delete(doc)
    db.commit()
    return True


def list_chunks(db: Session, kb_id: int, document_id: int) -> List[DocumentChunk]:
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.kb_id == kb_id, DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )


# ---------- 检索调试 ----------
def search_kb(db: Session, kb_id: int, query: str, top_k: int = 5) -> Tuple[str, List[dict]]:
    """向量检索调试入口；返回 (embedding 标识, hits)。P2.2 RAG 直接复用。"""
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise KBNotFoundError(f"知识库不存在: {kb_id}")
    embedder = get_embedder()
    vector = embedder.embed([query])[0]
    raw_hits = get_vector_store().query(_collection(kb_id), vector, top_k)
    hits = [
        {
            "content": h["document"],
            "score": round(h["score"], 4),
            "filename": h["metadata"].get("filename", ""),
            "chunk_index": h["metadata"].get("chunk_index", 0),
        }
        for h in raw_hits
    ]
    return embedder.name, hits
