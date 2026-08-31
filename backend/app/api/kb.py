"""知识库路由（P2.1）：/kb 系列接口

API 层只负责：JWT 鉴权、参数校验（文件类型/大小/空文件）、调用 service、
组装响应与异常映射；文档解析处理由 BackgroundTasks 执行。
"""
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import KB_ALLOWED_TYPES, KB_MAX_UPLOAD_SIZE
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.kb import (
    KBDetail,
    KBCreate,
    DocumentChunkInfo,
    DocumentInfo,
    KBInfo,
    KBSearchRequest,
    KBSearchResponse,
)
from app.services.kb_processor import process_document
from app.services.kb_service import (
    KBDuplicateError,
    KBNotFoundError,
    add_document,
    create_kb,
    delete_document,
    delete_kb,
    get_kb_detail,
    get_document,
    list_chunks,
    list_kbs,
    search_kb,
)

router = APIRouter()


def _doc_info(doc) -> DocumentInfo:
    return DocumentInfo.from_orm(doc)


# ---------- 知识库 ----------
@router.post("/kb", response_model=KBInfo)
def api_create_kb(
    payload: KBCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建知识库"""
    try:
        kb = create_kb(db, payload.name.strip(), payload.description)
    except KBDuplicateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "document_count": 0,
        "ready_count": 0,
        "created_at": kb.created_at,
    }


@router.get("/kb", response_model=list)
def api_list_kbs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """知识库列表（含文档统计）"""
    return list_kbs(db)


@router.get("/kb/{kb_id}", response_model=KBDetail)
def api_get_kb(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """知识库详情（含文档列表与处理状态）"""
    detail = get_kb_detail(db, kb_id)
    if not detail:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return detail


@router.delete("/kb/{kb_id}")
def api_delete_kb(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除知识库（级联删除文档、分块与向量数据）"""
    if not delete_kb(db, kb_id):
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"message": "知识库已删除"}


# ---------- 文档 ----------
@router.post("/kb/{kb_id}/documents", response_model=DocumentInfo)
def api_upload_document(
    kb_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传文档：校验 → 保存 → 创建 pending 记录 → 后台处理"""
    filename = file.filename or ""
    if "." not in filename or filename.rsplit(".", 1)[-1].lower() not in KB_ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，仅允许: {', '.join(KB_ALLOWED_TYPES)}",
        )
    data = file.file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(data) > KB_MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大 {KB_MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    try:
        doc = add_document(db, kb_id, filename, data)
    except KBNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 后台处理：解析 → 清洗 → chunk → embedding → 向量写入
    background_tasks.add_task(process_document, doc.id)
    return _doc_info(doc)


@router.delete("/kb/{kb_id}/documents/{document_id}")
def api_delete_document(
    kb_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除文档（级联删除分块与向量）"""
    if not delete_document(db, kb_id, document_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除"}


@router.get("/kb/{kb_id}/documents/{document_id}/chunks", response_model=list)
def api_list_chunks(
    kb_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查看文档分块（调试用）"""
    if not get_document(db, kb_id, document_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return list_chunks(db, kb_id, document_id)


# ---------- 检索调试 ----------
@router.post("/kb/{kb_id}/search", response_model=KBSearchResponse)
def api_search_kb(
    kb_id: int,
    payload: KBSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """知识库向量检索调试（P2.2 RAG 的基础）"""
    try:
        embedding_name, hits = search_kb(db, kb_id, payload.query.strip(), payload.top_k)
    except KBNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {e}")
    return {"query": payload.query, "embedding_model": embedding_name, "hits": hits}
