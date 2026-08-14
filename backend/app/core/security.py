import hashlib
import datetime
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.db.database import get_db


# 兼容保留（原 main.py L24-25）；注意：注册/登录实际使用 custom_hash_password
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# OAuth2 密码流 - tokenUrl 必须与实际登录路由一致
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


# ========== 密码哈希（与原 register/login 保持完全一致，使用自定义 hashlib）==========
_PASSWORD_SALT = "my_salt_123"


def custom_hash_password(password: str) -> str:
    """与 main.py 410-414、448-451 完全一致的哈希逻辑"""
    password_to_hash = f"{_PASSWORD_SALT}{password}{_PASSWORD_SALT}"
    return hashlib.sha256(password_to_hash.encode()).hexdigest()


def custom_verify_password(plain_password: str, hashed_password: str) -> bool:
    return custom_hash_password(plain_password) == hashed_password


# 保留原始签名（被其他模块引用时保持接口一致）
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return custom_verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return custom_hash_password(password)


# ========== JWT ==========
def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ========== 当前用户 ==========
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # 延迟导入避免循环依赖：core.security ⇄ services.auth_service
    from app.services.auth_service import get_user_by_username

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        print(f"[security] 收到的token: {token}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"[security] 解码后的payload: {payload}")
        username: str = payload.get("sub")
        print(f"[security] 获取到的用户名: {username}")
        if username is None:
            raise credentials_exception
    except JWTError as e:
        print(f"[security] JWT解码错误: {type(e).__name__}: {str(e)}")
        raise credentials_exception
    user = get_user_by_username(db, username=username)
    print(f"[security] 查询到的用户: {user}")
    if user is None:
        raise credentials_exception
    return user
