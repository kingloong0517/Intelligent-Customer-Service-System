# 直接测试密码哈希函数
from passlib.context import CryptContext

# 测试 bcrypt 算法
print("测试 bcrypt 算法...")
pwd_context_bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")

password = "123456"
print(f"密码: {password} (长度: {len(password)})")

# 直接测试哈希
try:
    hashed = pwd_context_bcrypt.hash(password)
    print(f"bcrypt 哈希成功: {hashed}")
    
    # 测试验证
    verified = pwd_context_bcrypt.verify(password, hashed)
    print(f"bcrypt 验证结果: {verified}")
except Exception as e:
    print(f"bcrypt 错误: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

# 测试 sha256_crypt 算法
print("\n测试 sha256_crypt 算法...")
pwd_context_sha256 = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# 直接测试哈希
try:
    hashed = pwd_context_sha256.hash(password)
    print(f"sha256_crypt 哈希成功: {hashed}")
    
    # 测试验证
    verified = pwd_context_sha256.verify(password, hashed)
    print(f"sha256_crypt 验证结果: {verified}")
except Exception as e:
    print(f"sha256_crypt 错误: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()