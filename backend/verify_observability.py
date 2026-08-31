#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4.1 可观测性验收脚本：Request ID / 日志链路 / /health / 敏感信息

覆盖检查项：
  1. /health 增强字段（database/embedding/llm_configured）
  2. Request ID：无头自动生成；客户端传入原样回写
  3. /chat 链路日志：同一 request_id 贯穿 route/rag/tool/llm/persist
  4. Tool 日志：tool_start / tool_result ok + duration_ms
  5. RAG 日志：used / top_score / hit_count / duration_ms（不含 chunk 内容）
  6. LLM 402 模拟：WARNING 日志 status_code=402 + 模板降级 + 前端无敏感信息
  7. 敏感信息扫描：日志中不出现假 API Key / Authorization / 密码

用法（在 backend 目录下）：
    .venv\\Scripts\\python.exe verify_observability.py

说明：使用独立测试库 test_obs.db，不触碰真实 chat.db；不发起真实 DeepSeek 请求。
"""
import json
import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 必须在 import app 之前设置：独立测试库 + 独立向量库/上传目录（与真实数据完全隔离，
# 避免测试 KB 与真实 KB 同 id 时覆盖/删除真实向量）；假 Key 仅用于敏感信息扫描
os.environ["DATABASE_URL"] = "sqlite:///./test_obs.db"
os.environ["VECTOR_STORE_DIR"] = os.path.join(BASE_DIR, "vector_store_test_obs")
os.environ["KB_UPLOAD_DIR"] = os.path.join(BASE_DIR, "uploads_test_obs")
os.environ["DEEPSEEK_API_KEY"] = "sk-obs-fake-secret-DO-NOT-LEAK-12345"
FAKE_KEY = os.environ["DEEPSEEK_API_KEY"]

sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
import app.services.chat_service as chat_service  # noqa: E402
import app.services.rag.rag_service as rag_svc  # noqa: E402
from app.services.llm import LLMError  # noqa: E402

# ---------- 日志捕获 ----------
captured = []


class ListHandler(logging.Handler):
    def emit(self, record):
        captured.append(self.format(record))


root = logging.getLogger()
handler = ListHandler()
handler.setFormatter(logging.Formatter("%(levelname)s %(name)s [request_id=%(request_id)s] %(message)s"))
root.addHandler(handler)

# LLM 全部 mock：模拟 DeepSeek 402（余额不足），验证降级与日志，不消耗额度
async def fake_402_stream(messages):
    raise LLMError("LLM 调用失败: APIStatusError: Error code: 402 - Insufficient Balance",
                   status_code=402)
    yield  # pragma: no cover

chat_service._llm_stream_chat = fake_402_stream

client = TestClient(app)
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -- {detail}" if detail else ""))


def logs_with(rid):
    return [ln for ln in captured if f"[request_id={rid}]" in ln]


def parse_sse(resp):
    events = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            try:
                events.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                pass
    return events


# ---------- 1. /health ----------
r = client.get("/health", headers={"X-Request-ID": "obs-health"})
j = r.json()
check("1./health 增强字段", r.status_code == 200 and j.get("status") == "ok"
      and "database" in j and "embedding" in j and "llm_configured" in j, json.dumps(j, ensure_ascii=False))
check("1b./health 回写 X-Request-ID", r.headers.get("x-request-id") == "obs-health")

# ---------- 2. Request ID ----------
r = client.get("/health")
auto_rid = r.headers.get("x-request-id")
check("2a.无 X-Request-ID 时自动生成", bool(auto_rid), f"auto={auto_rid}")
r = client.get("/health", headers={"X-Request-ID": "test-123"})
check("2b.客户端传入原样回写", r.headers.get("x-request-id") == "test-123")

# ---------- 3. 注册登录 ----------
uname = "obsuser"
client.post("/register", json={"username": uname, "password": "obs-pass-123"})
r = client.post("/login", data={"username": uname, "password": "obs-pass-123"})
token = r.json().get("access_token")
check("3.登录获取 JWT", bool(token))
H = {"Authorization": f"Bearer {token}"}
conv_id = client.post("/conversations", json={"title": "obs"}, headers=H).json()["id"]

# ---------- 4. /chat normal_chat：request_id 贯穿 route/llm/persist ----------
r = client.post("/chat", headers={**H, "X-Request-ID": "obs-normal"},
                json={"user_input": "你好呀", "conversation_id": conv_id, "category": "其他问题"})
rid_lines = logs_with("obs-normal")
joined = "\n".join(rid_lines)
check("4.normal_chat 同一 request_id 贯穿",
      r.status_code == 200
      and "route=normal_chat" in joined
      and "chat_persist=success" in joined
      and "request start: POST /chat" in joined
      and "request done: POST /chat" in joined,
      f"日志行数={len(rid_lines)}")

# ---------- 5. /chat Tool：tool_start/tool_result + duration ----------
r = client.post("/chat", headers={**H, "X-Request-ID": "obs-tool"},
                json={"user_input": "我的订单10001现在什么状态？", "conversation_id": conv_id,
                      "category": "订单咨询"})
rid_lines = logs_with("obs-tool")
joined = "\n".join(rid_lines)
check("5.单 Tool 日志链路",
      "route=order_query" in joined
      and "tool_start tool=order_query arguments={'order_id': '10001'}" in joined
      and "tool_result tool=order_query ok=True" in joined
      and "duration_ms=" in joined,
      f"tool 日志行={sum('tool_' in ln for ln in rid_lines)}")

# ---------- 6. /chat 多步 Tool：同一 request_id 贯穿两个 Tool ----------
r = client.post("/chat", headers={**H, "X-Request-ID": "obs-multi"},
                json={"user_input": "帮我查一下订单10001，如果已经发货，再告诉我物流到哪里了。",
                      "conversation_id": conv_id, "category": "订单咨询"})
rid_lines = logs_with("obs-multi")
joined = "\n".join(rid_lines)
order_ok = "tool_start tool=order_query" in joined and "tool_result tool=order_query ok=True" in joined
logi_ok = "tool_start tool=logistics_query" in joined and "tool_result tool=logistics_query ok=True" in joined
check("6.多步 Tool 同一 request_id 贯穿", order_ok and logi_ok and "chat_persist=success" in joined,
      f"order={order_ok} logistics={logi_ok}")

# ---------- 7. /chat RAG：rag 日志指标 ----------
# 建知识库 + 上传文档（BackgroundTasks 在 TestClient 中同步执行）
kb_id = client.post("/kb", json={"name": "obs-kb"}, headers=H).json()["id"]
files = {"file": ("售后政策.txt", "退款政策：用户收到商品后7天内可申请无理由退款，定制商品除外。".encode("utf-8"), "text/plain")}
client.post(f"/kb/{kb_id}/documents", files=files, headers=H)
# P5.1：hash fallback 相似度低，压低阈值驱动命中路径（与 verify_rag.py 一致），
# 验证 rag 日志指标与 SSE，而非 hash embedding 本身的相似度
_default_threshold = rag_svc.RAG_SIMILARITY_THRESHOLD
rag_svc.RAG_SIMILARITY_THRESHOLD = 0.01
try:
    r = client.post("/chat", headers={**H, "X-Request-ID": "obs-rag"},
                    json={"user_input": "退货退款规则是什么？", "conversation_id": conv_id,
                          "category": "售后问题"})
finally:
    rag_svc.RAG_SIMILARITY_THRESHOLD = _default_threshold
rid_lines = logs_with("obs-rag")
joined = "\n".join(rid_lines)
sse_text = r.text
check("7.RAG 日志与 SSE",
      "rag retrieve used=True" in joined and "top_score=" in joined
      and "hit_count=" in joined and "duration_ms=" in joined
      and '"used": true' in sse_text,
      f"rag 日志={sum('rag retrieve' in ln for ln in rid_lines)}")

# ---------- 8. LLM 402：降级 + 日志 + 前端安全 ----------
r = client.post("/chat", headers={**H, "X-Request-ID": "obs-402"},
                json={"user_input": "随便聊点啥", "conversation_id": conv_id, "category": "其他问题"})
rid_lines = logs_with("obs-402")
joined = "\n".join(rid_lines)
body = r.text
check("8.402 模板降级 + 日志状态码",
      "status_code=402" in joined and "fallback to template" in joined
      and "chat_persist=success" in joined
      and "Traceback" not in body and "Error code: 402" not in body,
      f"402 日志={sum('status_code=402' in ln for ln in rid_lines)}")

# ---------- 9. JWT ----------
r = client.get("/conversations")
check("9.无 Token 401", r.status_code == 401)

# ---------- 10. 敏感信息扫描 ----------
all_logs = "\n".join(captured)
leaks = [w for w in (FAKE_KEY, "sk-obs-fake", "Authorization", "Bearer sk-", "obs-pass-123") if w in all_logs]
check("10.日志无敏感信息（Key/密码/Authorization）", not leaks, f"leak={leaks}")

# ---------- 清理 ----------
client.delete(f"/conversations/{conv_id}", headers=H)
client.delete(f"/kb/{kb_id}", headers=H)

print()
passed = sum(1 for _, ok in results if ok)
print(f"===== 验收结果: {passed}/{len(results)} 通过 =====")
for name, ok in results:
    if not ok:
        print(f"失败项: {name}")
sys.exit(0 if passed == len(results) else 1)
