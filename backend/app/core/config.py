import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
project_backend_dir = os.path.dirname(os.path.dirname(current_dir))
load_dotenv(os.path.join(project_backend_dir, ".env"))


# ============== JWT ==============
# 优先从环境变量读取（生产必须配置强随机值），默认占位值仅用于本地开发兼容
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ============== DeepSeek API ==============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ============== LLM 服务（OpenAI 兼容协议，可整体替换为其他模型服务） ==============
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# P4.1：配置加载状态不在 import 期打印（此时日志未初始化），
# 由 main.create_app 统一记录 llm_configured=true/false（绝不输出 Key 值）；
# 运行时状态可通过 GET /health 查看（llm_configured 字段）。
if DEEPSEEK_API_KEY:
    os.environ["OPENAI_API_KEY"] = DEEPSEEK_API_KEY

# ============== 数据库 ==============
# 默认 SQLite 保持不变；支持通过 DATABASE_URL 环境变量切换（P2 MySQL 迁移使用）
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat.db")

# ============== 知识库（P2.1） ==============
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 上传的原始文档保存目录
KB_UPLOAD_DIR = os.getenv("KB_UPLOAD_DIR", os.path.join(BACKEND_DIR, "uploads", "kb"))
# 向量存储持久化目录
VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", os.path.join(BACKEND_DIR, "vector_store"))
# 上传文件大小上限（字节）
KB_MAX_UPLOAD_SIZE = int(os.getenv("KB_MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))
# 允许的文档类型
KB_ALLOWED_TYPES = ("pdf", "txt", "md")

# ============== Chunk 切分（P2.1） ==============
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))        # 单块最大字符数
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))   # 相邻块重叠字符数

# ============== Embedding（P2.1/P2.2） ==============
# provider: local=本地 sentence-transformers 中文模型（无需 API Key）；
#          auto=有 Key 用 OpenAI 兼容 API，否则本地模型（加载失败降级 hash）；
#          openai=强制 API；hash=强制本地哈希
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "auto")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
# OpenAI 兼容 embeddings 端点（如硅基流动 https://api.siliconflow.cn/v1、智谱等）；
# local provider 时该值为 HuggingFace 模型名（首次运行自动下载，之后读本地缓存）
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_TIMEOUT = float(os.getenv("EMBEDDING_TIMEOUT", "30"))
# 本地哈希降级向量维度
EMBEDDING_HASH_DIM = int(os.getenv("EMBEDDING_HASH_DIM", "256"))

# ============== RAG 接入 /chat（P2.2） ==============
# 检索 Top-K 条数
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
# 最低相似度阈值：最高分低于该值时不使用 RAG（避免强行喂无关内容）
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.45"))
# RAG context 中引用 snippet 的最大长度（citation 事件展示用）
RAG_SNIPPET_MAX_LEN = int(os.getenv("RAG_SNIPPET_MAX_LEN", "120"))

# ============== 多步 Tool 编排（P3.2） ==============
# 单次对话最大 Tool 调用次数，防止 Tool 链无限循环
MAX_TOOL_STEPS = int(os.getenv("MAX_TOOL_STEPS", "3"))

# ============== 日志（P4.1） ==============
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
