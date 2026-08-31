"""知识库文档处理流水线（P2.1）

上传 → 解析 → 清洗 → Chunk → Embedding → 向量写入 → 状态落库。
以 FastAPI BackgroundTasks 方式执行；使用独立 DB Session（不依赖请求生命周期）。
任何失败都会写入 documents.error_message，绝不静默失败。
"""
from typing import List

import logging

from app.core.config import CHUNK_OVERLAP, CHUNK_SIZE
from app.db.database import SessionLocal
from app.models.kb import Document, DocumentChunk
from app.services.rag.embedder import get_embedder
from app.services.rag.text_splitter import clean_text, chunk_text
from app.services.rag.vector_store import get_vector_store

logger = logging.getLogger("kb_processor")


def parse_file(file_path: str, file_type: str) -> str:
    """按类型解析原始文本；md/txt 误传为 Word 二进制时自动按 docx 解析"""
    if file_type == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text)
        return "\n".join(pages)

    # docx（Word）本质是 zip 容器：以 PK\x03\x04 魔数识别，
    # 防止用户将 .docx 改名为 .md/.txt 上传后按 UTF-8 读出整篇乱码
    with open(file_path, "rb") as f:
        magic = f.read(4)
    if magic == b"PK\x03\x04":
        return _parse_docx(file_path)

    # txt / md 统一按 UTF-8 读取，坏字节替换不中断
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _parse_docx(file_path: str) -> str:
    """提取 docx 正文文本：正文位于 word/document.xml，段落以 </w:p> 分隔（零额外依赖）"""
    import re as _re
    import zipfile

    with zipfile.ZipFile(file_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = xml.replace("<w:br/>", "\n").replace("<w:tab/>", "\t")
    xml = _re.sub(r"</w:p>", "\n", xml)
    text = _re.sub(r"<[^>]+>", "", xml)
    return text


def process_document(document_id: int) -> None:
    """后台处理入口：pending → processing → ready / failed"""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return
        doc.status = "processing"
        db.commit()

        try:
            # 1. 解析
            raw_text = parse_file(doc.file_path, doc.file_type)
            # 2. 清洗
            text = clean_text(raw_text)
            if not text:
                raise ValueError("文档解析后无有效文本内容")
            # 乱码防护：替换符比例过高说明文件内容与扩展名不符（如二进制被当文本读）
            bad_ratio = text.count("\ufffd") / max(len(text), 1)
            if bad_ratio > 0.05:
                raise ValueError(
                    f"文档解析乱码比例 {bad_ratio:.0%} 过高，文件内容可能与扩展名不符"
                )
            # 3. Chunk 切分
            chunks: List[str] = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            if not chunks:
                raise ValueError("文档切分后无有效分块")
            # 4. Embedding
            embedder = get_embedder()
            vectors = embedder.embed(chunks)
            # 5. 向量写入（单次全量 upsert，失败时无半写状态）
            store = get_vector_store()
            collection = f"kb_{doc.kb_id}"
            # 先清该文档旧向量（重处理场景块数可能变少，仅按 id upsert 会残留旧块）
            store.delete_where(collection, {"document_id": doc.id})
            chunk_keys = [f"d{doc.id}_c{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "kb_id": doc.kb_id,
                    "document_id": doc.id,
                    "chunk_index": i,
                    "filename": doc.filename,
                }
                for i in range(len(chunks))
            ]
            store.upsert(
                collection=collection,
                ids=chunk_keys,
                vectors=vectors,
                metadatas=metadatas,
                documents=chunks,
            )
            # 6. 分块落库（重处理场景先清旧块）+ 状态更新
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
            for i, (key, content) in enumerate(zip(chunk_keys, chunks)):
                db.add(
                    DocumentChunk(
                        document_id=doc.id,
                        kb_id=doc.kb_id,
                        chunk_index=i,
                        chunk_key=key,
                        content=content,
                        char_count=len(content),
                    )
                )
            doc.chunk_count = len(chunks)
            doc.embedding_model = embedder.name
            doc.status = "ready"
            doc.error_message = None
            db.commit()
            logger.info("document %s(%s) processed: %s chunks", doc.id, doc.filename, len(chunks))
        except Exception as e:
            # 失败：记录错误状态，不允许静默失败
            db.rollback()
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = f"{type(e).__name__}: {e}"[:500]
                db.commit()
            logger.error("document %s process failed: %s: %s", document_id, type(e).__name__, e)
    finally:
        db.close()
