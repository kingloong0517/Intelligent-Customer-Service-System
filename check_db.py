import sqlite3
import hashlib

print("===== 检查数据库用户记录 =====")

# 连接到 SQLite 数据库
conn = sqlite3.connect('backend/chat.db')
cursor = conn.cursor()

# 查询所有用户记录
print("\n查询所有用户记录：")
cursor.execute("SELECT id, username, password, created_at FROM users")
users = cursor.fetchall()

if users:
    for user in users:
        id, username, password, created_at = user
        print(f"\n用户ID: {id}")
        print(f"用户名: {username}")
        print(f"密码哈希: {password}")
        print(f"创建时间: {created_at}")
        
        # 测试密码验证
        test_password = "123456"
        hashed_test_password = hashlib.sha256(test_password.encode()).hexdigest()
        print(f"\n测试密码: {test_password}")
        print(f"测试密码哈希: {hashed_test_password}")
        print(f"密码匹配: {password == hashed_test_password}")
        
        # 测试其他可能的哈希算法
        print("\n尝试其他哈希算法：")
        # 测试 uppercase
        print(f"SHA256 大写: {hashed_test_password.upper()} 匹配: {password == hashed_test_password.upper()}")
        # 测试 lowercase
        print(f"SHA256 小写: {hashed_test_password.lower()} 匹配: {password == hashed_test_password.lower()}")
else:
    print("没有找到用户记录")

# 关闭数据库连接
conn.close()

print("\n===== 检查完成 =====")