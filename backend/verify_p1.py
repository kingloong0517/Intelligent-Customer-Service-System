#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1 验收脚本：真实 LLM 流式生成 + 事件化 SSE

覆盖检查项：
  1. 后端可启动（/health）          7.  无 API Key 模板降级
  2. 前端启动（另由 npm build 验证） 8.  JWT 鉴权（无 token/错 token/错密码）
  3. LLM 流式回答（--live 模式）    9.  多会话隔离
  4. Markdown 换行（mock LLM）     10. 历史消息落库 + 会话统计
  5. 中文不乱码                    11. SSE 正常结束（done 为最后事件）
  6. LLM API 异常降级              12. 客户端断开（部分内容落库）

用法（在 backend 目录下）：
    .venv\\Scripts\\python.exe verify_p1.py           # 降级/mock 场景，不依赖外网
    .venv\\Scripts\\python.exe verify_p1.py --live    # 追加真实 DeepSeek 流式验证

说明：全程使用独立测试库 test_p1.db（DATABASE_URL 环境变量），不触碰真实 chat.db。
"""
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 必须在 import app 之前设置：独立测试库 + 默认无 Key（降级路径）
os.environ["DATABASE_URL"] = "sqlite:///./test_p1.db"
if "--live" not in sys.argv:
    os.environ["DEEPSEEK_API_KEY"] = ""

sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
import app.services.chat_service as chat_service  # noqa: E402
import app.services.llm as llm_mod  # noqa: E402

ALL_TEMPLATES = {t for v in chat_service.CATEGORY_RESPONSES.values() for t in v}
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -- {detail}" if detail else ""))


def parse_sse(line_iter):
    """解析 SSE 流为 [(event, data_dict), ...]"""
    events, cur_event, data_lines = [], None, []
    for line in line_iter:
        line = line.rstrip("\r")
        if line == "":
            if cur_event is not None or data_lines:
                payload = json.loads("\n".join(data_lines)) if data_lines else {}
                events.append((cur_event or "message", payload))
            cur_event, data_lines = None, []
        elif line.startswith("event:"):
            cur_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip(" "))
    if cur_event is not None or data_lines:
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((cur_event or "message", payload))
    return events


def chat_sse(headers, user_input, conversation_id, category):
    with client.stream(
        "POST",
        "/chat",
        headers=headers,
        json={
            "user_input": user_input,
            "conversation_id": conversation_id,
            "category": category,
        },
    ) as resp:
        if resp.status_code != 200:
            return [(f"http_{resp.status_code}", {})]
        return parse_sse(resp.iter_lines())


def reply_of(events):
    return "".join(p.get("content", "") for k, p in events if k == "message")


client = TestClient(app)


def run():
    # ---------- 1. 启动 / 健康检查 ----------
    r = client.get("/health")
    check("1.后端启动 /health", r.status_code == 200 and r.json()["status"] == "ok")

    # ---------- 8. JWT ----------
    uname = f"p1user_{int(time.time())}"
    r = client.post("/register", json={"username": uname, "password": "test123456"})
    check("8a.注册", r.status_code == 200)
    r = client.post("/register", json={"username": uname, "password": "test123456"})
    check("8b.重复注册 400", r.status_code == 400)
    r = client.post("/login", data={"username": uname, "password": "wrong-pass"})
    check("8c.错误密码 401", r.status_code == 401)
    r = client.post("/login", data={"username": uname, "password": "test123456"})
    token = r.json().get("access_token", "")
    check("8d.登录返回 JWT", bool(token))
    H = {"Authorization": f"Bearer {token}"}
    r = client.get("/conversations")
    check("8e.无 token 401", r.status_code == 401)
    r = client.get("/conversations", headers={"Authorization": "Bearer bad-token"})
    check("8f.无效 token 401", r.status_code == 401)
    r = client.post("/chat", json={"user_input": "x", "conversation_id": 1})
    check("8g./chat 无 token 401", r.status_code == 401)

    # ---------- 9. 多会话 ----------
    c1 = client.post("/conversations", json={"title": "P1会话一"}, headers=H).json()
    c2 = client.post("/conversations", json={"title": "P1会话二"}, headers=H).json()
    check("9a.多会话创建", c1.get("id") and c2.get("id") and c1["id"] != c2["id"])
    r = client.post(
        "/chat",
        json={"user_input": "x", "conversation_id": 999999, "category": "其他问题"},
        headers=H,
    )
    check("9b.他人/不存在会话 404", r.status_code == 404)

    # ---------- 分类 ----------
    if "--live" in sys.argv:
        # init_db 已保证全新库自带默认分类；此处仅为防御性补齐（重名 400 静默忽略）
        _existing = {c["name"] for c in client.get("/categories").json()}
        for _name in ["账户问题", "订单咨询", "产品咨询", "售后问题", "其他问题"]:
            if _name not in _existing:
                client.post("/categories", json={"name": _name, "description": f"{_name}相关"})
    r = client.post("/ai-classify", json={"user_input": "我的订单什么时候发货"}, headers=H)
    cat = r.json().get("category")
    if "--live" in sys.argv:
        check("分类:命中预定义分类", cat in {"账户问题", "订单咨询", "产品咨询", "售后问题", "其他问题"}, f"实际={cat}")
    else:
        check("分类:订单咨询(含关键词兜底)", cat == "订单咨询", f"实际={cat}")

    # 以下场景强制走降级/mock 路径（live 模式下临时屏蔽真实 Key）
    real_key = llm_mod.DEEPSEEK_API_KEY
    llm_mod.DEEPSEEK_API_KEY = ""
    llm_mod._client = None

    # ---------- 5/7/11. 无 Key 降级 + SSE 协议 + 中文 ----------
    events = chat_sse(H, "我的订单什么时候发货？", c1["id"], "订单咨询")
    kinds = [k for k, _ in events]
    reply = reply_of(events)
    # P2.2 起 SSE 协议扩展：category 与 message 之间允许出现 rag/citation 事件；
    # P3.2 起进一步允许 tool_start/tool_result（如「我的订单什么时候发货」路由为 order_query）
    check(
        "11a.事件序列 category→[rag/citation/tool_start/tool_result]→message*→done",
        len(kinds) >= 3 and kinds[0] == "category" and kinds[-1] == "done"
        and set(kinds) <= {"category", "rag", "citation", "tool_start", "tool_result", "message", "done"},
        f"前3个={kinds[:3]}",
    )
    check("7.无Key降级为模板回复", reply in ALL_TEMPLATES, f"回复片段={reply[:20]}")
    check("5a.中文无乱码", "订单" in reply, f"回复={reply[:30]}")
    cat_data = next((p for k, p in events if k == "category"), {})
    check("category事件含intent字段", cat_data.get("category") == "订单咨询" and "intent" in cat_data)

    # ---------- 4. Markdown 换行（mock LLM 流） ----------
    async def fake_stream(messages):
        yield "## 订单说明\n\n"
        yield "- 第一条：**中文**内容正常\n"
        yield "- 第二条：你好，换行不丢失\n"

    orig = chat_service._llm_stream_chat
    chat_service._llm_stream_chat = fake_stream
    try:
        events = chat_sse(H, "测试Markdown输出", c1["id"], "产品咨询")
    finally:
        chat_service._llm_stream_chat = orig
    reply = reply_of(events)
    check("4a.Markdown换行保留(\\n\\n)", "\n\n" in reply and "- 第一条" in reply)
    check("4b.流式分片推送(多个message事件)", sum(1 for k, _ in events if k == "message") >= 3)
    check("11b.mock流done收尾", events[-1][0] == "done")

    # ---------- 10. 历史落库 + 会话统计 ----------
    done_data = events[-1][1]
    check("10a.done携带message_id", bool(done_data.get("message_id")))
    hist = client.get("/history", params={"conversation_id": c1["id"]}, headers=H).json()
    m = hist[-1] if hist else {}
    check(
        "10b.历史落库(问题+完整回复+分类)",
        m.get("user_input") == "测试Markdown输出" and m.get("ai_reply") == reply
        and m.get("category") == "产品咨询",
        f"落库长度={len(m.get('ai_reply') or '')}",
    )
    convs = client.get("/conversations", headers=H).json()
    conv1 = next((c for c in convs if c["id"] == c1["id"]), {})
    check("10c.会话统计 message_count", conv1.get("message_count") == 2, f"实际={conv1.get('message_count')}")

    # ---------- 6. LLM API 异常（连接失败 → 模板降级） ----------
    llm_mod.DEEPSEEK_API_KEY = "sk-invalid-for-failure-test"
    real_base_url = llm_mod.DEEPSEEK_BASE_URL
    llm_mod.DEEPSEEK_BASE_URL = "http://127.0.0.1:9"  # 必然连接失败
    llm_mod._client = None
    try:
        events = chat_sse(H, "随便问点什么", c2["id"], "其他问题")
    finally:
        llm_mod.DEEPSEEK_API_KEY = ""
        llm_mod.DEEPSEEK_BASE_URL = real_base_url
        llm_mod._client = None
    reply = reply_of(events)
    check("6.LLM连接失败→完整模板降级", reply in ALL_TEMPLATES and events[-1][0] == "done", f"回复={reply[:20]}")

    # ---------- 6b. 流中途失败 → error + done ----------
    async def failing_stream(messages):
        yield "部分内容已生成"
        raise llm_mod.LLMError("模拟流中途失败")

    chat_service._llm_stream_chat = failing_stream
    try:
        events = chat_sse(H, "测试中途失败", c2["id"], "其他问题")
    finally:
        chat_service._llm_stream_chat = orig
    kinds = [k for k, _ in events]
    check(
        "6b.流中途失败:error+done且done最后",
        "error" in kinds and kinds[-1] == "done" and "部分内容已生成" in reply_of(events),
        str(kinds),
    )

    # ---------- 12. 客户端断开 ----------
    with client.stream(
        "POST",
        "/chat",
        headers=H,
        json={"user_input": "测试断开连接", "conversation_id": c2["id"], "category": "其他问题"},
    ) as resp:
        n = 0
        for _line in resp.iter_lines():
            n += 1
            if n >= 4:  # 读完 category 块 + 首个 message 块后断开
                break
    time.sleep(1.5)  # 等待服务端 finally 落库
    hist2 = client.get("/history", params={"conversation_id": c2["id"]}, headers=H).json()
    m2 = next((x for x in hist2 if x.get("user_input") == "测试断开连接"), {})
    check(
        "12.客户端断开后已生成内容落库",
        bool(m2.get("ai_reply")),
        f"落库长度={len(m2.get('ai_reply') or '')}",
    )

    # ---------- 9c. 会话隔离 ----------
    h1 = client.get("/history", params={"conversation_id": c1["id"]}, headers=H).json()
    h2 = client.get("/history", params={"conversation_id": c2["id"]}, headers=H).json()
    ids1 = {x["user_input"] for x in h1}
    ids2 = {x["user_input"] for x in h2}
    check(
        "9c.两会话消息互相隔离",
        "测试断开连接" not in ids1 and "测试Markdown输出" not in ids2,
    )

    # ---------- 3. 真实 LLM（--live） ----------
    if "--live" in sys.argv:
        llm_mod.DEEPSEEK_API_KEY = real_key  # 恢复真实 Key
        llm_mod._client = None
        # 预检：账户余额不足（402）/网络不可达时跳过，降级链路已由场景 4/6/6b 覆盖
        try:
            import asyncio as _asyncio

            _asyncio.run(anext(llm_mod.stream_chat([{"role": "user", "content": "hi"}])))
        except llm_mod.LLMError as e:
            print(f"[SKIP] 3.真实LLM流式（上游不可用: {e}；请检查账户余额/网络后重试）")
            return
        events = chat_sse(H, "请用Markdown列表列出两个网购注意事项", c1["id"], "产品咨询")
        reply = reply_of(events)
        check("3a.真实LLM流式回复非空", len(reply) > 10, f"前50字={reply[:50]}")
        check("3b.真实LLM含Markdown换行", "\n" in reply)
        check("3c.非模板回复", reply not in ALL_TEMPLATES)
    else:
        print("[SKIP] 3.真实LLM流式（使用 --live 运行以启用，需配置 DEEPSEEK_API_KEY）")


if __name__ == "__main__":
    try:
        run()
    finally:
        client.close()
        try:
            os.remove(os.path.join(BASE_DIR, "test_p1.db"))
        except OSError:
            pass

    failed = [n for n, ok in results if not ok]
    print(f"\n===== 验收结果: {len(results) - len(failed)}/{len(results)} 通过 =====")
    if failed:
        print("失败项: " + "; ".join(failed))
        sys.exit(1)
    print("全部通过")
