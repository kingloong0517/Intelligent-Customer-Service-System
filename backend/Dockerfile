# backend/Dockerfile - AI 客服后端（FastAPI + 本地 Embedding）
# 基础版本与本地开发环境一致（Python 3.11）
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# 先单独安装 CPU 版 torch（避免 sentence-transformers 拉入 CUDA 全家桶，
# 镜像体积从 ~7GB 降到 ~2GB）。如网络受限可替换：
#   pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 依赖层（requirements.txt 未变时不重建）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码（.dockerignore 已排除 .env / 数据库 / uploads / vector_store）
COPY . .

# 运行时数据目录：由 docker compose 挂载卷提供持久化
#   /app/data          → SQLite（DATABASE_URL=sqlite:////app/data/chat.db）
#   /app/uploads       → 知识库上传文档（KB_UPLOAD_DIR）
#   /app/vector_store  → 向量库（VECTOR_STORE_DIR）
#   /app/hf_cache      → HuggingFace 模型缓存（BAAI/bge-small-zh-v1.5）
RUN mkdir -p /app/data /app/uploads/kb /app/vector_store /app/hf_cache \
    && useradd -m appuser \
    && chown -R appuser /app

# HF 缓存默认指向挂载目录（compose 中亦可覆盖）；首次启动自动下载模型，
# 之后 embedder.py 检测到缓存会自动 HF_HUB_OFFLINE=1 离线加载
ENV HF_HOME=/app/hf_cache \
    HF_HUB_CACHE=/app/hf_cache/hub

USER appuser

EXPOSE 8000

# P4.1 /health：不调用 DeepSeek（不消耗额度），覆盖 FastAPI/database/vector_store
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

# 启动命令与本地一致：backend/main.py 暴露 app.main:app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
