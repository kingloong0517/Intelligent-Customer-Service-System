"""
backend 入口 - 启动命令保持不变：
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
把 FastAPI 实例从 app.main 包暴露出来，业务代码全在 app/ 内。
"""
from app.main import app  # noqa: F401
