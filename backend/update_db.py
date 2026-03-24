import sqlite3

print("===== 更新数据库表结构 =====")

# 连接到 SQLite 数据库
conn = sqlite3.connect('chat.db')
cursor = conn.cursor()

# 检查并删除旧表
try:
    cursor.execute("DROP TABLE chat_messages")
    print("已删除旧的 chat_messages 表")
except Exception as e:
    print(f"删除表时出错: {e}")

# 关闭数据库连接
conn.close()

print("\n请重新启动后端服务以创建新表")
print("===== 更新完成 =====")