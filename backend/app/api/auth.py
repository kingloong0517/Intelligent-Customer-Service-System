"""
认证路由：/register、/login
路径、请求方式、响应结构与原 main.py 401-470 完全一致
"""
import datetime
import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.security import create_access_token, custom_verify_password
from app.db.database import get_db
from app.schemas.auth import Token, UserCreate, UserInfo
from app.services.auth_service import create_user, get_user_by_username

router = APIRouter()


@router.post("/register", response_model=UserInfo)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = get_user_by_username(db, username=user.username)
        if db_user:
            raise HTTPException(status_code=400, detail="用户名已存在")

        print(f"[api/auth] 注册密码: {user.password}")
        db_user = create_user(db, username=user.username, password=user.password)
        return UserInfo.from_orm(db_user)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[api/auth] 注册错误详情: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        user = get_user_by_username(db, username=form_data.username)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 与原 447-458 一致的自定义哈希校验
        if not custom_verify_password(form_data.password, user.password):
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[api/auth] 登录错误详情: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise
