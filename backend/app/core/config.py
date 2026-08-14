import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
project_backend_dir = os.path.dirname(os.path.dirname(current_dir))
load_dotenv(os.path.join(project_backend_dir, ".env"))


# ============== JWT ==============
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ============== DeepSeek API ==============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

if DEEPSEEK_API_KEY:
    os.environ["OPENAI_API_KEY"] = DEEPSEEK_API_KEY
    # 避免打印密钥，仅输出加载状态
    print(f"[config] DEEPSEEK_API_KEY 已从 .env 加载 (长度={len(DEEPSEEK_API_KEY)})")
else:
    print("[config] 警告: DEEPSEEK_API_KEY 未设置，请在 backend/.env 中配置")

# ============== SQLite ==============
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"
