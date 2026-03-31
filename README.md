# AI 客服系统

这是一个完整的 AI 客服系统，采用前后端分离架构，专为企业提供智能客服解决方案。系统集成了问题分类、会话管理、智能回复等核心客服功能，帮助企业高效处理客户咨询。

## 技术栈

- **前端**: Vue 3 + Vite + Element Plus
- **后端**: Python + FastAPI
- **数据库**: SQLite

## 项目结构

```
ai_chat/
├── backend/                  # 后端代码
│   ├── main.py               # FastAPI 主应用，包含所有API接口
│   ├── requirements.txt      # 依赖列表
│   ├── .env                  # 环境变量配置
│   ├── .env.example          # 环境变量示例
│   ├── chat.db               # SQLite数据库
│   └── __pycache__/          # Python编译缓存
├── frontend/                 # 前端代码
│   ├── index.html            # HTML 入口
│   ├── package.json          # 前端依赖
│   ├── package-lock.json     # 依赖锁定文件
│   ├── vite.config.js        # Vite 配置
│   ├── dist/                 # 构建输出目录
│   └── src/                  # 前端源码
│       ├── main.js           # Vue 入口
│       ├── App.vue           # 主组件
│       ├── router/           # 路由配置
│       └── views/            # 页面组件
│           ├── Chat.vue      # 聊天界面
│           ├── Login.vue     # 登录界面
│           └── Register.vue  # 注册界面
├── .venv/                    # Python虚拟环境
├── .vscode/                  # VS Code配置
└── README.md                 # 项目说明
```

## 后端配置与运行

### 1. 安装依赖

使用虚拟环境安装依赖：

```bash
# 创建虚拟环境（如果尚未创建）
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 安装依赖
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写智谱GLM API Key：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

编辑 `.env` 文件：

```
ZHIPU_API_KEY=your_zhipu_api_key_here
```

### 3. 运行后端服务

```bash
# 在backend目录下
uvicorn main:app --reload

# 或在项目根目录下
uvicorn backend.main:app --reload
```

后端服务将在 `http://127.0.0.1:8000` 运行。

## 前端配置与运行

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 运行前端服务

```bash
npm run dev
```

前端服务将在 `http://localhost:3000` 运行。

### 3. 构建前端项目

```bash
npm run build
```

构建输出将保存在 `frontend/dist` 目录中。

## API 接口

### 用户认证接口

#### POST /register
用户注册

**请求体**:
```json
{
  "username": "用户名",
  "password": "密码"
}
```

**响应**:
```json
{
  "id": 1,
  "username": "用户名",
  "created_at": "2024-01-01T00:00:00"
}
```

#### POST /login
用户登录

**请求体**:
```json
{
  "username": "用户名",
  "password": "密码"
}
```

**响应**:
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

### 会话管理接口

#### GET /conversations
获取用户所有会话

**响应**:
```json
[
  {
    "id": 1,
    "title": "会话标题",
    "user_id": 1,
    "status": "active",
    "last_message": "最后一条消息预览...",
    "message_count": 5,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
]
```

#### POST /conversations
创建新会话

**请求体**:
```json
{
  "title": "会话标题"
}
```

**响应**:
```json
{
  "id": 1,
  "title": "会话标题",
  "user_id": 1,
  "status": "active",
  "last_message": null,
  "message_count": 0,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### DELETE /conversations/{conversation_id}
删除会话

**响应**:
```json
{
  "message": "会话已删除"
}
```

#### PUT /conversations/{conversation_id}/status
更新会话状态

**请求体**:
```json
{
  "status": "active|ended|archived"
}
```

**响应**:
```json
{
  "message": "会话状态已更新",
  "conversation": {
    "id": 1,
    "title": "会话标题",
    "user_id": 1,
    "status": "ended",
    "last_message": "最后一条消息预览...",
    "message_count": 5,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

### 聊天接口

#### POST /chat
发送消息并获取 AI 回复（流式输出）

**请求体**:
```json
{
  "user_input": "你的问题",
  "conversation_id": 1,
  "category": "账户问题"
}
```

**响应**:
```
data: 你
data: 好
data: ！
data: [DONE]
```

### 问题分类接口

#### POST /ai-classify
**新增**：AI 自动分类接口，自动识别用户问题所属分类

**请求体**:
```json
{
  "user_input": "你的问题内容"
}
```

**响应**:
```json
{
  "category": "账户问题"
}
```

#### GET /categories
获取所有分类

**响应**:
```json
[
  {
    "id": 1,
    "name": "账户问题",
    "description": "登录、注册、密码等相关问题",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  },
  {
    "id": 2,
    "name": "订单咨询",
    "description": "下单、支付、物流等相关问题",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
]
```

#### POST /categories
创建新分类

**请求体**:
```json
{
  "name": "新分类",
  "description": "分类描述"
}
```

**响应**:
```json
{
  "id": 6,
  "name": "新分类",
  "description": "分类描述",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### GET /categories/{category_id}
获取单个分类

**响应**:
```json
{
  "id": 1,
  "name": "账户问题",
  "description": "登录、注册、密码等相关问题",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### PUT /categories/{category_id}
更新分类

**请求体**:
```json
{
  "name": "更新后的分类名称",
  "description": "更新后的分类描述"
}
```

**响应**:
```json
{
  "id": 1,
  "name": "更新后的分类名称",
  "description": "更新后的分类描述",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### DELETE /categories/{category_id}
删除分类

**响应**:
```json
{
  "message": "分类已删除"
}
```

## 功能说明

### 核心客服功能

1. **AI 自动问题分类**：
   - 预设5个常用分类：账户问题、订单咨询、产品咨询、售后问题、其他问题
   - **新增**：AI 自动识别用户问题并分类，无需手动选择
   - 支持自定义添加、修改、删除分类
   - 显示最近使用的分类，方便快速选择
   - 每条消息自动显示对应的分类标签

2. **会话管理**：
   - 创建、查看、删除会话
   - 会话状态管理：进行中、已结束、已归档
   - 显示会话最后一条消息预览
   - 统计会话消息数量
   - 支持修改会话状态

3. **智能客服回复**：
   - 集成智谱GLM API，提供智能回复
   - **新增**：根据不同问题分类，使用不同风格的回答
     - 账户问题：专业严谨的风格
     - 订单咨询：详细查询的风格
     - 产品咨询：产品介绍的风格
     - 售后问题：道歉解决的风格
     - 其他问题：通用友好的风格
   - 流式输出，逐字显示回复内容
   - 每条消息显示对应的分类标签

4. **用户认证**：
   - 用户注册功能
   - JWT 认证登录
   - 安全的密码哈希存储

5. **数据持久化**：
   - 所有聊天记录保存到 SQLite 数据库
   - 会话信息、分类信息持久化存储
   - 分类信息和消息关联存储

### 技术特性

1. **前后端分离架构**：前端和后端完全分离，通过 API 进行通信
2. **响应式设计**：适配不同屏幕尺寸，支持移动端访问
3. **实时更新**：会话状态和消息数量实时更新
4. **开发便捷**：支持热重载，提高开发效率
5. **向后兼容**：支持现有数据，无需数据迁移

## 客服工作流程

1. **用户登录**：用户通过注册或登录进入系统
2. **创建会话**：用户创建新的聊天会话
3. **发送消息**：用户输入并发送问题
4. **AI 自动分类**：系统自动识别问题所属的分类（账户问题/订单咨询/产品咨询/售后问题/其他问题）
5. **AI 智能回复**：系统根据分类结果，使用对应风格生成智能回复
   - 账户问题：专业严谨的风格
   - 订单咨询：详细查询的风格
   - 产品咨询：产品介绍的风格
   - 售后问题：道歉解决的风格
   - 其他问题：通用友好的风格
6. **查看记录**：用户可查看历史聊天记录
7. **结束会话**：问题解决后，用户可将会话标记为已结束
8. **归档管理**：对于已解决的会话，可进行归档处理

## 注意事项

1. 确保你已经拥有智谱GLM API Key，可在智谱AI官网申请。
2. 前端服务通过 Vite 代理将 `/api` 请求转发到后端 `http://127.0.0.1:8000`。
3. 在生产环境中，建议修改 CORS 配置，只允许特定的前端域名访问后端 API。
4. 首次运行时，系统会自动创建数据库表和默认分类数据。
5. 使用虚拟环境可以避免依赖冲突，建议在开发时使用虚拟环境。

## 开发说明

### 后端开发

后端使用 FastAPI 框架，主要功能包括：
- 聊天接口实现（支持流式输出）
- 数据库模型定义（用户、会话、消息、分类）
- JWT 认证与授权
- 智谱GLM API 集成
- **新增**：AI 自动分类接口，实现问题自动识别
- **新增**：基于分类结果的不同风格回答生成
- 环境变量配置
- 异常处理与日志记录
- CORS 支持
- 问题分类管理接口
- 会话状态管理

### 前端开发

前端使用 Vue 3 + Element Plus，主要功能包括：
- 响应式聊天界面设计
- **新增**：AI 自动分类功能集成，无需手动选择分类
- 用户登录与注册页面
- 会话列表与管理
- 消息发送与接收（支持流式显示）
- 自动分类标签显示（无需手动选择）
- 会话状态展示
- 聊天记录展示（含分类标签）
- API 调用封装
- 实时更新与状态管理

## 数据库结构

### 用户表（users）
- id: 主键
- username: 用户名
- password_hash: 密码哈希值
- created_at: 创建时间

### 会话表（conversations）
- id: 主键
- title: 会话标题
- user_id: 外键，关联用户表
- status: 会话状态（active, ended, archived）
- last_message: 最后一条消息预览
- message_count: 消息数量
- created_at: 创建时间
- updated_at: 更新时间

### 聊天消息表（chat_messages）
- id: 主键
- conversation_id: 外键，关联会话表
- user_input: 用户输入
- ai_response: AI 回复
- category: 问题分类
- created_at: 创建时间

### 分类表（categories）
- id: 主键
- name: 分类名称
- description: 分类描述
- created_at: 创建时间
- updated_at: 更新时间