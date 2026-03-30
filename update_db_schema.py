import sqlite3
import datetime

# 连接到数据库
conn = sqlite3.connect('backend/chat.db')
cursor = conn.cursor()

# 检查chat_messages表是否已经有category字段
try:
    # 尝试获取表的所有列
    cursor.execute("PRAGMA table_info(chat_messages)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'category' not in column_names:
        # 添加category字段
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN category TEXT")
        print("成功添加category字段到chat_messages表")
    else:
        print("category字段已经存在于chat_messages表中")
        
    # 提交更改
    conn.commit()
    print("数据库更新完成")
    
except Exception as e:
    print(f"更新数据库时出错: {e}")
    conn.rollback()

finally:
    # 关闭连接
    conn.close()
