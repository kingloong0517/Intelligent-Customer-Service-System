# AI 客服系统

企业级 AI 智能客服平台：前后端分离、分层架构、自动问题分类、SSE 流式对话、会话与分类管理。

> 项目已完成工程化重构（功能零变化）：原单体 `main.py` 拆分为 `core/db/models/schemas/services/api` 分层；前端 API 调用统一封装；密钥通过环境变量管理。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite 4 + Element Plus + Vue Router + Axios |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + PyJWT + python-multipart + requests |
| 数据库 | SQLite（`chat.db`，自动建表 + 结构迁移 + 数据回填） |
| AI | DeepSeek API（问题分类 + 智能回复，含关键词兜底） |
| 流式 | Server-Sent Events（SSE 逐字输出） |

## 项目结构

```
ai_chat/
├── backend/
│   ├── main.py                       # 入口壳，从 app.main 导入 app
│   ├── requirements.txt              # 依赖清单
│   ├── .env                          # 环境变量（含 DEEPSEEK_API_KEY，不入库）
│   ├── .env.example                  # 环境变量示例
│   ├── chat.db                       # SQLite 数据库（首次启动自动生成）
│   └── app/                          # 应用包
│       ├── __init__.py
│       ├── main.py                   # FastAPI 工厂函数：创建 app + CORS + 路由注册 + 启动时建表
│       ├── api/                      # API 路由层（只处理 HTTP、注入依赖、捕获异常）
│       │   ├── __init__.py
│       │   ├── auth.py               # /register, /login
│       │   ├── categories.py         # GET/POST/PUT/DELETE /categories*
│       │   ├── chat.py               # /chat (SSE), /ai-classify
│       │   └── conversations.py      # /conversations*, /messages, /history
│       ├── core/                     # 横切关注点：配置、安全
│       │   ├── __init__.py
│       │   ├── config.py             # 统一配置（JWT/DB/DeepSeek）
│       │   └── security.py           # JWT 创建、密码哈希、get_current_user
│       ├── db/                       # 数据库基础：连接、初始化、迁移
│       │   ├── __init__.py
│       │   ├── database.py           # SQLAlchemy engine / Session / Base
│       │   └── init_db.py            # 建表 + 列迁移 + 消息统计回填 + 分类时间戳回填
│       ├── models/                   # SQLAlchemy ORM 模型（与原表结构 1:1）
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── conversation.py
│       │   ├── category.py
│       │   └── message.py
│       ├── schemas/                  # Pydantic 请求/响应 DTO
│       │   ├── __init__.py
│       │   ├── auth.py               # UserCreate, UserInfo, Token
│       │   ├── chat.py               # ChatRequest, Message, ChatHistory
│       │   ├── conversation.py       # ConversationCreate, ConversationInfo
│       │   └── category.py           # CategoryCreate, CategoryUpdate, CategoryInfo
│       └── services/                 # 业务逻辑层（可单元测试，不感知 HTTP）
│           ├── __init__.py
│           ├── auth_service.py       # get_user_by_username / create_user（密码哈希）
│           ├── chat_service.py       # 模板化 AI 回复（按分类选风格）+ SSE 迭代器
│           ├── classification.py     # DeepSeek AI 分类 + 关键词兜底
│           └── conversation.py       # 会话/消息/历史 CRUD + 状态校验
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js                # /api 代理 → http://127.0.0.1:8000
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/index.js
│       ├── utils/
│       │   └── request.js            # axios 封装（token 注入 + 401 自动登出）
│       ├── api/                      # 前后端 API 契约层
│       │   ├── auth.js               # login / register / logout / syncGlobalAuthorization
│       │   ├── categories.js         # getCategories / createCategory / updateCategory / deleteCategory
│       │   ├── chat.js               # aiClassify / chatStream（流式 fetch）
│       │   └── conversations.js      # getConversations / createConversation / deleteConversation / updateConversationStatus / getMessages / getHistory
│       └── views/
│           ├── Login.vue
│           ├── Register.vue
│           └── Chat.vue
├── .vscode/launch.json
└── README.md
```

## 快速启动

### 后端

```bash
# 1. 虚拟环境 & 依赖
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# 或直接使用 venv 的 Python：.venv\Scripts\python.exe

cd backend
pip install -r requirements.txt

# 2. 环境变量（复制示例后填入真实 Key）
copy .env.example .env
# 编辑 backend/.env：DEEPSEEK_API_KEY=sk-xxxxxxxx

# 3. 启动（自动建表 + 初始化 5 个默认分类 + 回填历史空值字段）
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger UI：http://127.0.0.1:8000/docs
- OpenAPI JSON：http://127.0.0.1:8000/openapi.json

### 前端

```bash
cd frontend
npm install
npm run dev          # 开发：http://localhost:3000
npm run build        # 生产构建 → dist/
```

## 接口总览（15 条业务路由，路径与原项目零变化）

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| POST | /register | 用户注册 | 否 |
| POST | /login | OAuth2 form 登录，返回 JWT | 否 |
| GET | /health | 健康检查 | 否 |
| GET | /categories | 分类列表 | 否 |
| GET | /categories/{category_id} | 分类详情 | 否 |
| POST | /categories | 新建分类 | 是 |
| PUT | /categories/{category_id} | 更新分类 | 是 |
| DELETE | /categories/{category_id} | 删除分类 | 是 |
| GET | /conversations | 当前用户会话列表 | 是 |
| POST | /conversations | 新建会话 | 是 |
| DELETE | /conversations/{id} | 删除会话（级联删消息） | 是 |
| PUT | /conversations/{id}/status | 更新会话状态 | 是 |
| POST | /ai-classify | AI 自动问题分类 | 是 |
| POST | /chat | 发送消息 → SSE 流式回复 | 是 |
| GET | /messages | 消息列表（旧接口） | 是 |
| GET | /history | 聊天历史（含用户/AI/分类） | 是 |

> 详细请求/响应结构见 `docs/api.md`（如单独创建）。

## 核心功能与实现要点

### 1. 密码哈希（兼容旧数据）
统一使用 `hashlib.sha256(salt + password + salt)`，salt = `"my_salt_123"`。
- 注册与登录使用完全相同的算法；
- `auth_service` 与 `core/security` 均实现该算法（前者避免引入循环依赖，后者用于登录校验）。

### 2. JWT 认证
- `create_access_token(data, expires_delta)`：使用 PyJWT，HS256；
- `get_current_user`：FastAPI `Depends`，校验 token → 取 username → 查 DB → 返回 User；
- 内部对 `auth_service` 做**延迟导入**解决 `core.security ⇄ services.auth_service` 的循环依赖。

### 3. 数据库初始化（向后兼容）
`init_database()` 在启动时自动执行，对老 DB 无破坏性：
1. `create_all` 建不存在的表；
2. 对 `chat_messages` / `conversations` 老表若缺少 `category / category_id / status / last_message / message_count` 字段，逐个 `ALTER TABLE ADD COLUMN`；
3. 根据消息表回填所有会话的 `message_count` / `last_message`；
4. 若 `categories` 不存在则建表并插入 5 个默认分类（含时间戳）；
5. **回填遗留 NULL 时间戳**：对早期用裸 SQL 插入的分类行，若 `created_at IS NULL OR updated_at IS NULL` 则用当前时间写入；
6. 自动打印 `users` 表字段用于自检。

### 4. AI 自动分类
`services/classification.ai_classify(db, user_input)`：
- 取 DB 中 categories → 拼 prompt → 调 DeepSeek chat completion；
- 无 Key / HTTP 失败 / 解析失败 → 关键词规则兜底（登录/注册→账户，订单/支付→订单，产品/使用→产品，售后/退款→售后，否则→其他）；
- 兜底可脱离网络运行，保证功能闭环。

### 5. 流式对话（SSE）
`POST /chat` 使用 FastAPI `StreamingResponse`，MIME=`text/event-stream`：
1. 先将 `(用户输入, 空回复, 分类)` 写入 `chat_messages` 拿到 `message_id`；
2. `services/chat_service` 按分类挑模板 → 组合完整回答 → 按**字符**切成 chunk；
3. 每 0.04s yield `data: <chunk>\n\n`，最后 `data: [DONE]`；
4. 流式结束前 `UPDATE chat_messages SET response=? WHERE id=?` 持久化 AI 回复；
5. 同时更新会话的 `message_count` 与 `last_message`。

### 6. 前端请求统一封装
`utils/request.js`：
- `baseURL = '/api'`（Vite 代理到后端 8000）；
- `request` 实例拦截器：请求前自动从 `localStorage.token` 注入 `Authorization: Bearer …`；
- 响应拦截：若 `401` 则清 token 并跳转登录页；
- `syncGlobalAuthorization()`：同步**全局** `axios.defaults.headers.common.Authorization`（兼容 Chat.vue 内 `fetch` 直连与历史场景）。

## 环境变量（backend/.env）

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- 变量名保持 `DEEPSEEK_API_KEY`（与原约定一致，未改动 Key 名称）；
- 仅从 `backend/.env` 读取（python-dotenv 加载），**不** 写入任何代码；
- 如未配置 Key，系统仍可运行：AI 分类自动切换关键词兜底，聊天使用内置模板回复。

## 测试与验证

重构完成后执行的校验：

| 验证项 | 结果 |
|---|---|
| FastAPI 路由 import（冷启动无循环依赖） | ✅ |
| openapi.json 注册的业务路径数（15 条，GET/POST/PUT/DELETE） | ✅ 15 |
| `POST /register` → `POST /login` → JWT 注入后续请求 | ✅ |
| 重复注册（400）/ 错密码（401）/ 无 token（401） | ✅ |
| 分类列表/详情/新建/更新/删除 → 时间戳回填 NULL | ✅ |
| 会话创建/列表/更新状态/级联删除 → message_count/last_message 同步 | ✅ |
| AI 分类 5 用例（登录/订单/产品/售后/其他） | ✅ 全命中 |
| `POST /chat` SSE 流式逐字 + `[DONE]` 结束 | ✅ Content-Type: text/event-stream |
| `/messages` + `/history` schema 字段完整性 | ✅ |
| `GET /health` | ✅ |
| 前端 `npm run build` | ✅ 通过（仅 chunk size 非致命警告） |

## 注意事项

1. **CORS**：当前允许 `*` 仅用于开发，生产请在 `app/main.py` CORSMiddleware 中收紧 `allow_origins`；
2. **JWT Secret**：`core/config.SECRET_KEY` 有默认占位值，生产务必替换为强随机值（或从环境变量读）；
3. **Vite 代理**：`vite.config.js` 将 `/api` → `http://127.0.0.1:8000` 并 **剥离 `/api` 前缀**，与后端路由（根级 `/chat` 等）天然匹配；
4. **SSE + nginx**：若前置 nginx，需关闭缓冲 `proxy_buffering off;`，否则浏览器收不到逐字 chunk；
5. **密码迁移**：自定义 hashlib 实现与历史数据完全一致；若切换到 bcrypt/argon2 需要额外的迁移策略（本次未变）。
