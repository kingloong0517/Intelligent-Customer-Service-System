"""
main.py - 入口装配：
  - 创建 FastAPI app
  - CORS
  - 注册 Router
  - 启动时调用数据库初始化（建表 + 迁移 + 默认分类）
业务逻辑全部下沉至 api/services/models/schemas/db/core。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.db.init_db import init_database


def create_app() -> FastAPI:
    app = FastAPI(title="AI Chat", description="AI 智能客服聊天系统", version="1.0.0")

    # CORS（与原 77-83 完全一致）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 数据库初始化（建表 + 迁移 ALTER TABLE + 默认分类）
    init_database()

    # 路由注册：注意每个 router 内部直接写完整路径，不使用 prefix，确保 API 路径零变化
    app.include_router(auth_router)
    app.include_router(conversations_router)
    app.include_router(categories_router)
    app.include_router(chat_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "ai-chat"}

    return app


app = create_app()
