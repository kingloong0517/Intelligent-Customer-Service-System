# AI 聊天网站项目

这是一个完整的 AI 聊天网站项目，采用前后端分离架构。

## 技术栈

- **前端**: Vue 3 + Vite + Element Plus
- **后端**: Python + FastAPI
- **数据库**: SQLite

## 项目结构

```
ai_chat/
├── backend/           # 后端代码
│   ├── main.py        # FastAPI 主应用
│   ├── requirements.txt  # 依赖列表
│   └── .env.example   # 环境变量示例
├── frontend/          # 前端代码
│   ├── index.html     # HTML 入口
│   ├── package.json   # 前端依赖
│   ├── vite.config.js # Vite 配置
│   └── src/           # 前端源码
│       ├── main.js    # Vue 入口
│       └── App.vue    # 主组件
└── README.md          # 项目说明
```

## 后端配置与运行

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写 OpenAI API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 运行后端服务

```bash
uvicorn main:app --reload
```

后端服务将在 `http://localhost:8000` 运行。

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

## API 接口

### POST /chat

发送消息并获取 AI 回复。

**请求体**:
```json
{
  "user_input": "你的问题"
}
```

**响应**:
```json
{
  "reply": "AI 回复"
}
```

### GET /messages

获取所有聊天记录。

**响应**:
```json
[
  {
    "id": 1,
    "message": "你的问题",
    "response": "AI 回复",
    "created_at": "2023-06-01T12:00:00"
  }
]
```

## 功能说明

1. **用户输入消息，AI 返回回复**：前端发送消息到后端，后端调用 OpenAI API 获取回复并返回。
2. **聊天记录保存**：所有聊天记录都会保存到 SQLite 数据库中。
3. **前后端分离**：前端和后端完全分离，通过 API 进行通信。

## 注意事项

1. 确保你已经拥有 OpenAI API Key。
2. 前端服务通过 Vite 代理将 `/api` 请求转发到后端 `http://localhost:8000`。
3. 在生产环境中，建议修改 CORS 配置，只允许特定的前端域名访问后端 API。

## 开发说明

### 后端开发

后端使用 FastAPI 框架，主要功能包括：
- 聊天接口实现
- 数据库模型定义
- 环境变量配置
- 异常处理
- CORS 支持

### 前端开发

前端使用 Vue 3 + Element Plus，主要功能包括：
- 聊天界面设计
- 消息发送与接收
- 聊天记录展示
- API 调用封装