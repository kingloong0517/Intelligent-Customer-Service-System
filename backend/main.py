from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import os
import requests
import datetime
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import JWTError, jwt

# JWT 配置
SECRET_KEY = "your-secret-key-change-in-production"  # 生产环境中应该使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码哈希上下文
# 临时使用更简单的 sha256_crypt 代替 bcrypt，避免长度限制问题
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# OAuth2 密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# 加载环境变量
load_dotenv()

# 配置智谱 GLM API
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 配置数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 创建应用
app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库模型
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    message = Column(String, index=True)
    response = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# 创建数据库表
Base.metadata.create_all(bind=engine)
print("数据库表创建完成")
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"现有表: {tables}")
if 'users' in tables:
    print("users表字段:", inspector.get_columns('users'))

# 密码哈希和验证函数
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# 用户相关函数
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, username: str, password: str):
    hashed_password = get_password_hash(password)
    db_user = User(username=username, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# JWT token 相关函数
def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

# Pydantic 模型
# 用户相关模型
class UserCreate(BaseModel):
    username: str
    password: str

class UserInfo(BaseModel):
    id: int
    username: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 聊天相关模型
class ChatRequest(BaseModel):
    user_input: str
    conversation_id: int

class ChatResponse(BaseModel):
    reply: str

class Message(BaseModel):
    id: int
    message: str
    response: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# 会话相关模型
class ConversationBase(BaseModel):
    title: str

class ConversationCreate(ConversationBase):
    pass

class ConversationInfo(ConversationBase):
    id: int
    user_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# 用户要求的历史记录模型格式
class ChatHistory(BaseModel):
    id: int
    user_input: str
    ai_reply: str
    timestamp: datetime.datetime
    conversation_id: int

    class Config:
        orm_mode = True
    
    @classmethod
    def from_orm(cls, obj):
        # 手动映射字段
        return cls(
            id=obj.id,
            user_input=obj.message,
            ai_reply=obj.response,
            timestamp=obj.created_at,
            conversation_id=obj.conversation_id
        )

# 用户注册接口
@app.post("/register", response_model=UserInfo)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # 检查用户名是否已存在
        db_user = get_user_by_username(db, username=user.username)
        if db_user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        # 完全自定义密码哈希（不依赖任何外部库）
        import hashlib
        # 创建一个简单但足够的哈希
        salt = "my_salt_123"  # 实际生产环境应该使用随机盐
        password_to_hash = f"{salt}{user.password}{salt}"
        hashed_password = hashlib.sha256(password_to_hash.encode()).hexdigest()
        
        print(f"注册密码: {user.password}")
        print(f"哈希后密码: {hashed_password}")
        
        # 创建新用户
        db_user = User(username=user.username, password=hashed_password)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return UserInfo.from_orm(db_user)
    except Exception as e:
        print(f"注册错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")

# 用户登录接口
@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        # 验证用户
        user = get_user_by_username(db, username=form_data.username)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 使用与注册完全相同的密码哈希逻辑
        import hashlib
        salt = "my_salt_123"  # 必须与注册时使用的盐相同
        password_to_hash = f"{salt}{form_data.password}{salt}"
        hashed_password = hashlib.sha256(password_to_hash.encode()).hexdigest()
        
        if hashed_password != user.password:
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 创建访问令牌
        access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        print(f"登录错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

# 会话管理接口
# 获取会话列表
@app.get("/conversations", response_model=List[ConversationInfo])
def get_conversations(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # 获取当前用户的所有会话
    conversations = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).all()
    return conversations

# 创建新会话
@app.post("/conversations", response_model=ConversationInfo)
def create_conversation(conversation: ConversationCreate, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # 创建新会话
    db_conversation = Conversation(
        user_id=current_user.id,
        title=conversation.title
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation

# 删除会话
@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # 查找会话
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 删除相关的聊天记录
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).delete()
    
    # 删除会话
    db.delete(conversation)
    db.commit()
    
    return {"message": "会话已删除"}

import asyncio

# 聊天接口 - 需要认证（流式输出）
@app.post("/chat")
def chat(chat_request: ChatRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # 验证会话是否属于当前用户
        conversation = db.query(Conversation).filter(
            Conversation.id == chat_request.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            return Response(content="会话不存在", status_code=404)
            
        # 临时使用模拟数据（用于演示）
        mock_responses = [
            "你好！我是 AI 助手，可以帮助您解答问题。",
            "这个问题很有趣，让我思考一下...",
            "根据我的了解，这个问题的答案是...",
            "非常感谢您的提问，我很乐意为您提供帮助。",
            "您的问题涉及到多个方面，让我逐一分析。",
            "从不同的角度来看，这个问题可以有不同的答案。",
            "我认为最合理的解释是...",
            "希望我的回答能够帮助到您！",
            "如果您还有其他问题，随时可以继续问我。",
            "这个问题比较复杂，让我详细说明一下。"
        ]
        # 根据用户输入生成不同的回复
        reply_index = hash(chat_request.user_input) % len(mock_responses)
        reply = mock_responses[reply_index]
        
        # 生成器函数，逐字返回响应
        async def generate():
            # 逐字发送回复
            for char in reply:
                yield f"data: {char}\n\n"
                await asyncio.sleep(0.1)  # 减慢发送速度，让逐字效果更明显
            
            # 发送完成标记
            yield "data: [DONE]\n\n"
        
        # 保存聊天记录到数据库（关联当前用户和会话）
        chat_message = ChatMessage(
            user_id=current_user.id,
            conversation_id=chat_request.conversation_id,
            message=chat_request.user_input,
            response=reply
        )
        db.add(chat_message)
        
        # 更新会话的更新时间
        conversation.updated_at = datetime.datetime.utcnow()
        
        db.commit()
        db.refresh(chat_message)
        
        # 返回流式响应
        return StreamingResponse(generate(), media_type="text/event-stream")
    except HTTPException as e:
        return Response(content=str(e.detail), status_code=e.status_code)
    except Exception as e:
        # 处理其他错误
        return Response(content=f"服务器错误: {str(e)}", status_code=500)

# 获取聊天记录接口（旧接口，保持兼容）- 需要认证
@app.get("/messages", response_model=List[Message])
def get_messages(current_user = Depends(get_current_user), conversation_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # 构建查询
    query = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id)
    
    # 如果提供了会话 ID，按会话过滤
    if conversation_id:
        # 验证会话是否属于当前用户
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        query = query.filter(ChatMessage.conversation_id == conversation_id)
    
    # 按时间排序
    messages = query.order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    return messages

# 获取聊天记录接口（新接口，符合用户要求的字段名称）- 需要认证
@app.get("/history", response_model=List[ChatHistory])
def get_chat_history(current_user = Depends(get_current_user), conversation_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # 构建查询
    query = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id)
    
    # 如果提供了会话 ID，按会话过滤
    if conversation_id:
        # 验证会话是否属于当前用户
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        query = query.filter(ChatMessage.conversation_id == conversation_id)
    
    # 按时间倒序排列
    messages = query.order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    
    # 手动转换为 ChatHistory 模型
    return [ChatHistory.from_orm(msg) for msg in messages]