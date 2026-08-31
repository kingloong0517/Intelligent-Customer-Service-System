"""重建 VectorStore：使用 venv python，用 BGE 重新 Embedding"""
import sys, os, json, math
sys.path.insert(0, r'd:\vscode program\ai_chat\backend')
os.chdir(r'd:\vscode program\ai_chat\backend')

from app.services.rag.embedder import get_embedder
from app.services.rag.vector_store import get_vector_store
from app.db.database import SessionLocal
from app.models.kb import Document, DocumentChunk, KnowledgeBase

# 1. 检查 embedder
emb = get_embedder()
print(f'Embedder: {emb.name}, dim={emb.dim}, class={emb.__class__.__name__}')
assert 'hash' not in emb.name.lower(), 'Still using hash embedder!'

db = SessionLocal()
vs = get_vector_store()

try:
    kbs = db.query(KnowledgeBase).all()
    print(f'\nKBs: {len(kbs)}')
    
    for kb in kbs:
        print(f'\n--- KB id={kb.id} name={kb.name} ---')
        
        # 清空旧向量
        vs.delete_collection(f'kb_{kb.id}')
        
        # 从 DB 读已有 chunks
        chunks = db.query(DocumentChunk).filter(DocumentChunk.kb_id == kb.id).order_by(DocumentChunk.chunk_index).all()
        print(f'  DB chunks: {len(chunks)}')
        
        if not chunks:
            print('  No chunks in DB, skipping')
            continue
        
        # 准备数据
        texts = []
        metadatas = []
        for c in chunks:
            texts.append(c.content)
            metadatas.append({
                'filename': c.document.filename if c.document else '',
                'document_id': c.document_id,
                'chunk_index': c.chunk_index,
            })
        
        # 生成新向量
        print(f'  Generating embeddings for {len(texts)} chunks...')
        vectors = emb.embed(texts)
        
        # L2 normalize
        for v in vectors:
            norm = math.sqrt(sum(x*x for x in v))
            if norm > 0:
                for i in range(len(v)):
                    v[i] /= norm
        
        # 写入 VectorStore
        ids = [c.chunk_key for c in chunks]
        vs.upsert(
            collection=f'kb_{kb.id}',
            ids=ids,
            vectors=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        
        print(f'  Upserted {len(vectors)} vectors (BGE {emb.dim}d)')
        
        # 更新 DB 中 document 的 embedding_model
        doc_ids = set(c.document_id for c in chunks)
        for did in doc_ids:
            doc = db.query(Document).filter(Document.id == did).first()
            if doc:
                doc.embedding_model = emb.name
        db.commit()
        print(f'  Updated embedding_model in DB')

finally:
    db.close()

print('\n=== VectorStore rebuilt! ===')

# 快速验证
print('\n=== Quick RAG test ===')
db2 = SessionLocal()
try:
    from app.services.kb_service import search_kb
    for kb in db2.query(KnowledgeBase).all():
        model, hits = search_kb(db2, kb.id, '退货退款规则是什么？', top_k=3)
        print(f'KB {kb.id} search: model={model}')
        for h in hits:
            print(f'  score={h["score"]:.4f} file={h["filename"]} text={h["content"][:50]}...')
finally:
    db2.close()
