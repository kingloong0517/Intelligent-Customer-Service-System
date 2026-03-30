import sqlite3

print("===== 更新会话表结构 =====")

# 连接到 SQLite 数据库
conn = sqlite3.connect('backend/chat.db')
cursor = conn.cursor()

try:
    # 检查conversations表是否已经有status字段
    cursor.execute("PRAGMA table_info(conversations)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    # 添加status字段
    if 'status' not in column_names:
        cursor.execute("ALTER TABLE conversations ADD COLUMN status TEXT DEFAULT 'active'")
        print("已添加status字段到conversations表")
    else:
        print("conversations表已包含status字段")
    
    # 添加last_message字段
    if 'last_message' not in column_names:
        cursor.execute("ALTER TABLE conversations ADD COLUMN last_message TEXT")
        print("已添加last_message字段到conversations表")
    else:
        print("conversations表已包含last_message字段")
    
    # 添加message_count字段
    if 'message_count' not in column_names:
        cursor.execute("ALTER TABLE conversations ADD COLUMN message_count INTEGER DEFAULT 0")
        print("已添加message_count字段到conversations表")
    else:
        print("conversations表已包含message_count字段")
    
    # 更新现有数据
    print("更新现有会话的message_count...")
    # 获取每个会话的消息数量
    cursor.execute("SELECT conversation_id, COUNT(*) FROM chat_messages GROUP BY conversation_id")
    conversation_message_counts = cursor.fetchall()
    
    for conversation_id, count in conversation_message_counts:
        # 更新消息数量
        cursor.execute("UPDATE conversations SET message_count = ? WHERE id = ?", (count, conversation_id))
        
        # 获取最后一条消息
        cursor.execute("SELECT message FROM chat_messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1", (conversation_id,))
        last_message = cursor.fetchone()
        if last_message:
            # 截取消息预览（最多50个字符）
            preview = last_message[0][:50] + "..." if len(last_message[0]) > 50 else last_message[0]
            cursor.execute("UPDATE conversations SET last_message = ? WHERE id = ?", (preview, conversation_id))
    
    print(f"已更新 {len(conversation_message_counts)} 个会话的消息数量和最后消息预览")
    
    # 提交更改
    conn.commit()
    print("\n数据库更新完成")
    
except Exception as e:
    print(f"更新表结构时出错: {e}")
    conn.rollback()

finally:
    # 关闭连接
    conn.close()
    
print("===== 更新结束 =====")
