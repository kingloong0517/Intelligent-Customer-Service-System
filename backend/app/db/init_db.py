"""
数据库初始化：建表 + 结构迁移（向后兼容补字段） + 默认分类
逻辑与原 main.py 124-235 完全一致，保留全部 ALTER TABLE 兼容逻辑。
"""
import datetime

from sqlalchemy import inspect, text

# 必须先导入所有模型，确保 Base.metadata.tables 有全部定义
from app.db.database import Base, engine
from app.models.user import User  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.message import ChatMessage  # noqa: F401


DEFAULT_CATEGORIES = [
    ("账户问题", "登录、注册、密码等相关问题"),
    ("订单咨询", "下单、支付、物流等相关问题"),
    ("产品咨询", "产品功能、使用方法等相关问题"),
    ("售后问题", "退换货、维修等相关问题"),
    ("其他问题", "其他类型的咨询"),
]


def init_database() -> None:
    # 1. 建表
    Base.metadata.create_all(bind=engine)
    print("[init_db] 数据库表创建完成")

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[init_db] 现有表: {tables}")

    # 2. chat_messages: 补 category 字段
    if "chat_messages" in tables:
        chat_columns = inspector.get_columns("chat_messages")
        chat_column_names = [col["name"] for col in chat_columns]

        if "category" not in chat_column_names:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN category VARCHAR"))
                conn.commit()
            print("[init_db] 已添加category字段到chat_messages表")
        else:
            print("[init_db] chat_messages表已包含category字段")

        # 2.1 chat_messages: 补 category_id 字段
        chat_columns = inspector.get_columns("chat_messages")
        chat_column_names = [col["name"] for col in chat_columns]
        with engine.connect() as conn:
            if "category_id" not in chat_column_names:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN category_id INTEGER"))
                conn.commit()
                print("[init_db] 已添加category_id字段到chat_messages表")
            else:
                print("[init_db] chat_messages表已包含category_id字段")

    # 3. conversations: 补 status / last_message / message_count 字段
    if "conversations" in tables:
        conv_columns = inspector.get_columns("conversations")
        conv_column_names = [col["name"] for col in conv_columns]

        with engine.connect() as conn:
            if "status" not in conv_column_names:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN status VARCHAR DEFAULT 'active'"))
                conn.commit()
                print("[init_db] 已添加status字段到conversations表")
            else:
                print("[init_db] conversations表已包含status字段")

            if "last_message" not in conv_column_names:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN last_message VARCHAR"))
                conn.commit()
                print("[init_db] 已添加last_message字段到conversations表")
            else:
                print("[init_db] conversations表已包含last_message字段")

            if "message_count" not in conv_column_names:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN message_count INTEGER DEFAULT 0"))
                conn.commit()
                print("[init_db] 已添加message_count字段到conversations表")
            else:
                print("[init_db] conversations表已包含message_count字段")

            # 更新现有会话的 message_count / last_message
            print("[init_db] 更新现有会话的message_count和last_message...")
            conn.execute(text("""
                UPDATE conversations SET
                    message_count = (SELECT COUNT(*) FROM chat_messages WHERE chat_messages.conversation_id = conversations.id),
                    last_message = (SELECT SUBSTR(message, 1, 50) || CASE WHEN LENGTH(message) > 50 THEN '...' ELSE '' END
                                    FROM chat_messages
                                    WHERE chat_messages.conversation_id = conversations.id
                                    ORDER BY created_at DESC LIMIT 1)
            """))
            conn.commit()
            print("[init_db] 已更新所有会话的消息数量和最后消息预览")

    # 4. categories 表 + 默认分类
    if "categories" not in tables:
        Base.metadata.tables["categories"].create(bind=engine)
        print("[init_db] 已创建categories表")

        with engine.connect() as conn:
            now = datetime.datetime.utcnow().isoformat()
            for name, description in DEFAULT_CATEGORIES:
                conn.execute(
                    text(
                        "INSERT INTO categories (name, description, created_at, updated_at) "
                        "VALUES (:name, :desc, :ca, :ua)"
                    ),
                    {"name": name, "desc": description, "ca": now, "ua": now},
                )
            conn.commit()
        print(f"[init_db] 已添加 {len(DEFAULT_CATEGORIES)} 个默认分类")
    else:
        print("[init_db] categories表已存在")

    # 4.1 回填历史遗留 NULL 时间戳（由裸 SQL INSERT 导致的 created_at/updated_at 为空）
    with engine.connect() as conn:
        now = datetime.datetime.utcnow().isoformat()
        result = conn.execute(
            text(
                "UPDATE categories SET created_at = :ca, updated_at = :ua "
                "WHERE created_at IS NULL OR updated_at IS NULL"
            ),
            {"ca": now, "ua": now},
        )
        updated = result.rowcount
        if updated:
            conn.commit()
            print(f"[init_db] 已回填 {updated} 行 categories 的 NULL 时间戳")

    if "users" in tables:
        print("[init_db] users表字段:", [c["name"] for c in inspector.get_columns("users")])
