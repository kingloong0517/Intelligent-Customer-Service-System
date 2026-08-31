#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性重建向量：Embedding 模型切换后，对存量 ready 文档重新生成向量

用法（backend 目录下）：
    python rebuild_embeddings.py

- 不重新上传文件，直接使用 document_chunks 中的现有分块；
- 每个文档先按 document_id 删除旧向量再写入新向量，
  确保 VectorStore 中不存在不同模型产生的混合向量；
- 同步更新 documents.embedding_model；
- 重建失败的文档：删除其全部旧向量并标记 failed，同样避免混用。

执行后输出：文档数量 / Chunk 数量 / 成功数 / 失败数 / embedding 模型 / 向量总数。
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.db.database import SessionLocal  # noqa: E402
from app.models.kb import Document, DocumentChunk  # noqa: E402
from app.services.rag.embedder import get_embedder  # noqa: E402
from app.services.rag.vector_store import get_vector_store  # noqa: E402


def main():
    db = SessionLocal()
    docs_ok, docs_fail, chunk_total = 0, 0, 0
    vector_total = 0
    doc_total = 0
    model_name = ""
    try:
        embedder = get_embedder()
        model_name = embedder.name
        store = get_vector_store()
        docs = db.query(Document).filter(Document.status == "ready").all()
        doc_total = len(docs)
        print(f"Embedding 模型: {embedder.name} (dim={embedder.dim})")
        print(f"待处理 ready 文档: {doc_total} 个")
        print("-" * 64)

        kb_ids = set()
        for doc in docs:
            kb_ids.add(doc.kb_id)
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            chunk_total += len(chunks)
            if not chunks:
                print(f"[跳过] 文档 {doc.id}({doc.filename}): 无分块")
                continue
            collection = f"kb_{doc.kb_id}"
            try:
                texts = [c.content for c in chunks]
                vectors = embedder.embed(texts)
                chunk_keys = [f"d{doc.id}_c{i}" for i in range(len(chunks))]
                metadatas = [
                    {
                        "kb_id": doc.kb_id,
                        "document_id": doc.id,
                        "chunk_index": c.chunk_index,
                        "filename": doc.filename,
                    }
                    for c in chunks
                ]
                # 先删该文档全部旧向量（旧模型维度），再写入新向量 → 禁止混用
                store.delete_where(collection, {"document_id": doc.id})
                store.upsert(collection, chunk_keys, vectors, metadatas, texts)
                doc.embedding_model = embedder.name
                db.commit()
                docs_ok += 1
                print(f"[OK]   文档 {doc.id}({doc.filename}): {len(chunks)} chunks -> {embedder.name}")
            except Exception as e:
                db.rollback()
                docs_fail += 1
                # 失败同样清掉旧向量并标记 failed，避免新旧模型向量混用
                try:
                    store.delete_where(collection, {"document_id": doc.id})
                    d = db.query(Document).filter(Document.id == doc.id).first()
                    if d:
                        d.status = "failed"
                        d.error_message = f"rebuild failed: {type(e).__name__}: {e}"[:500]
                        db.commit()
                except Exception:
                    pass
                print(f"[FAIL] 文档 {doc.id}({doc.filename}): {type(e).__name__}: {e}")

        for kb_id in sorted(kb_ids):
            n = store.count(f"kb_{kb_id}")
            vector_total += n
            print(f"VectorStore kb_{kb_id}: {n} 条向量")
    finally:
        db.close()

    print("-" * 64)
    print(
        f"文档数量: {doc_total}  Chunk 数量: {chunk_total}  "
        f"成功: {docs_ok}  失败: {docs_fail}  向量总数: {vector_total}"
    )
    print(f"Embedding 模型: {model_name}")
    if docs_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
