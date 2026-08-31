import sys, os
sys.path.insert(0, r'd:\vscode program\ai_chat\backend')
os.chdir(r'd:\vscode program\ai_chat\backend')

from app.services.rag.embedder import get_embedder

print('=== EMBEDDER CHECK ===')
emb = get_embedder()
print(f'name={emb.name}, dim={emb.dim}, class={emb.__class__.__name__}')

test = emb.embed(['退货退款规则是什么？'])
print(f'embed ok, len={len(test)}, vec_len={len(test[0]) if test else 0}, first5={test[0][:5] if test else []}')

print('\n=== RECREATE VECTOR STORE ===')
from app.services.kb_service import get_all_knowledge_bases, get_documents_of_kb
from app.services.rag.vector_store import VectorStore
from app.services.rag.kb_processor import split_document  # maybe wrong name
from app.db.database import SessionLocal
from app.models import Document

db = SessionLocal()
try:
    kbs = get_all_knowledge_bases(db)
    print(f'Found {len(kbs)} knowledge bases')
    for kb in kbs:
        print(f'\n  KB id={kb.id} name={kb.name}')
        docs = db.query(Document).filter(Document.knowledge_base_id == kb.id).all()
        print(f'  Documents: {len(docs)}')
        for d in docs:
            print(f'    doc id={d.id} name={d.filename} content_len={len(d.content) if d.content else 0}')
finally:
    db.close()
