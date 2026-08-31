import hashlib

from sqlalchemy.orm import Session

from app.models.user import User


_PASSWORD_SALT = "my_salt_123"


def _custom_hash_password(password: str) -> str:
    """与 core/security 中实现完全一致（同 salt、同算法），但此处不 import 避免循环依赖"""
    payload = f"{_PASSWORD_SALT}{password}{_PASSWORD_SALT}"
    return hashlib.sha256(payload.encode()).hexdigest()


def get_user_by_username(db: Session, username: str) -> User:
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, username: str, password: str) -> User:
    """自定义 hashlib 哈希（与 core/security 同算法，历史数据兼容）"""
    hashed_password = _custom_hash_password(password)

    db_user = User(username=username, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
