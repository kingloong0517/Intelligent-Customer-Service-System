import sqlite3

print("===== 添加分类字段到数据库表 =====")

# 连接到 SQLite 数据库
conn = sqlite3.connect('chat.db')
cursor = conn.cursor()

try:
    # 检查chat_messages表是否已经有category字段
    cursor.execute("PRAGMA table_info(chat_messages)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'category' not in column_names:
        # 添加category字段
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN category TEXT")
        print("成功添加category字段到chat_messages表")
        conn.commit()
    else:
        print("category字段已经存在于chat_messages表中")
        
except Exception as e:
    print(f"更新表结构时出错: {e}")
    conn.rollback()

# 关闭数据库连接
conn.close()

print("===== 更新完成 =====")
