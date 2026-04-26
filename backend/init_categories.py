import sqlite3

# 连接到数据库
conn = sqlite3.connect('chat.db')
cursor = conn.cursor()

# 检查categories表是否有数据
cursor.execute('SELECT * FROM categories')
existing_categories = cursor.fetchall()

if not existing_categories:
    # 添加默认分类
    default_categories = [
        ('账户问题', '与账户相关的问题，如登录、注册、密码重置等'),
        ('订单咨询', '与订单相关的问题，如订单状态、发货、支付等'),
        ('产品咨询', '与产品相关的问题，如产品功能、使用方法等'),
        ('售后问题', '与售后服务相关的问题，如退货、换货、维修等'),
        ('其他问题', '其他类型的问题')
    ]
    
    cursor.executemany('INSERT INTO categories (name, description) VALUES (?, ?)', default_categories)
    conn.commit()
    print('已添加默认分类')
else:
    print('分类数据已存在')

# 关闭连接
conn.close()
