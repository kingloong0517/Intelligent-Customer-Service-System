"""
main.py - 入口装配：
  - 统一日志初始化（P4.1）
  - 创建 FastAPI app
  - Request ID 中间件（P4.1：X-Request-ID 透传/生成 + 响应头回写 + 请求日志）
  - 全局异常兜底（P4.1：日志记录详情，前端只收到安全错误）
  - CORS
  - 注册 Router
  - 健康检查（P4.1：database/embedding/vector_store/llm_configured，不调用 DeepSeek）
  - 启动时调用数据库初始化（建表 + 迁移 + 默认分类）
业务逻辑全部下沉至 api/services/models/schemas/db/core。
"""
import logging
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.kb import router as kb_router
from app.core.config import (
    DEEPSEEK_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LOG_LEVEL,
    SECRET_KEY,
    VECTOR_STORE_DIR,
)

from app.core.logging_config import request_id_var, setup_logging
from app.db.init_db import init_database

# P5.1 P0-1：SECRET_KEY 默认占位值安全检查
# 生产环境必须配置强随机 SECRET_KEY，否则 JWT 可被伪造（此处只警告，不阻断启动，
# 避免破坏本地开发与现有功能）
_DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"

setup_logging(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("app.main")


class RequestIDMiddleware:
    """纯 ASGI 中间件（非 BaseHTTPMiddleware，SSE 流式零缓冲风险）：

    - 优先使用客户端 X-Request-ID，否则服务端生成 UUID；
    - request_id 写入 contextvar，链路日志自动携带；
    - 响应头回写 X-Request-ID；
    - 记录请求开始/完成日志（含耗时）。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers") or []}
        rid = (headers.get("x-request-id") or "").strip() or uuid.uuid4().hex
        token = request_id_var.set(rid)
        method = scope.get("method", "")
        path = scope.get("path", "")
        start = time.perf_counter()
        logger.info("request start: %s %s", method, path)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
                # CORS 中间件已在更外层，此处仅追加，不影响既有响应头
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.info("request done: %s %s duration_ms=%d", method, path, duration_ms)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)


def create_app() -> FastAPI:
    app = FastAPI(title="AI Chat", description="AI 智能客服聊天系统", version="1.0.0")

    # 统一配置加载状态（P4.1：只记录 configured，绝不打印 Key 值）
    logger.info("config loaded: llm_configured=%s embedding_provider=%s", bool(DEEPSEEK_API_KEY), EMBEDDING_PROVIDER)
    # P5.1 P0-1：SECRET_KEY 默认占位值警告（生产必须配置强随机值，否则 JWT 可被伪造）
    if SECRET_KEY == _DEFAULT_SECRET_KEY:
        logger.warning(
            "SECRET_KEY 使用默认占位值，生产环境必须配置强随机 SECRET_KEY，否则 JWT 可被伪造"
        )

    # CORS（与原 77-83 完全一致）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Request ID 全链路（P4.1）：注册在 CORS 之后，响应头两者都会带上
    app.add_middleware(RequestIDMiddleware)

    # 全局异常兜底（P4.1）：详细错误只进日志（自动带 request_id），
    # 前端只收到安全信息；不破坏 SSE 内部已有的 error 事件协议
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):
        logger.error(
            "unhandled error: %s %s error=%s: %s",
            request.method, request.url.path, type(exc).__name__, exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "服务器内部错误，请稍后重试"},
        )

    # 数据库初始化（建表 + 迁移 ALTER TABLE + 默认分类）
    init_database()

    # 路由注册：注意每个 router 内部直接写完整路径，不使用 prefix，确保 API 路径零变化
    app.include_router(auth_router)
    app.include_router(conversations_router)
    app.include_router(categories_router)
    app.include_router(chat_router)
    app.include_router(kb_router)

    @app.get("/health")
    def health():
        # P4.1 轻量可观测健康检查：不调用 DeepSeek（不消耗额度），
        # llm_configured 仅反映配置是否存在；402 余额问题不影响本接口
        health_info = {
            "status": "ok",
            "app": "ai-chat",
            "database": "ok",
            "embedding": f"{EMBEDDING_PROVIDER}:{EMBEDDING_MODEL}",
            "llm_configured": bool(DEEPSEEK_API_KEY),
        }
        try:
            from app.db.database import SessionLocal
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
            finally:
                db.close()
        except Exception as e:
            logger.error("health database check failed: %s", e)
            health_info["status"] = "degraded"
            health_info["database"] = "error"
        try:
            import os as _os
            health_info["vector_store"] = "ok" if _os.path.isdir(VECTOR_STORE_DIR) else "empty"
        except Exception:
            health_info["vector_store"] = "unknown"
        return health_info

    return app


app = create_app()
