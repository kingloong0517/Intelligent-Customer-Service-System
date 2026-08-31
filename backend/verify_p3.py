#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P3.1/P3.2 验收脚本：Agent Router 五路由 + 多步 Tool 编排（P4.1 回归补充）

覆盖检查项（verify_observability.py 未覆盖的 P3 场景）：
  1. 闲聊短路        → route=normal_chat（无 rag/tool 事件）
  2. human_service   → 固定转接文案，不调 LLM、无 tool 事件
  3. logistics_query 独立路由（无订单号 → ok=False missing_order_id）
  4. logistics_query 带订单号命中（10001）
  5. fail-fast：订单非「已发货」（10002 待付款）→ 不接力 logistics
  6. fail-fast：订单存在但无 tracking_no → 不接力 logistics
  7. Tool 失败：订单不存在 → ok=False not_found，链路终止
  8. 多步链式：order_query(10001 已发货) → logistics_query
  9. 路由优先级：同时含订单+物流词 → order_query 先行（数据上游）

用法（在 backend 目录下）：
    .venv\\Scripts\\python.exe verify_p3.py

说明：独立测试库 test_p3.db + 独立向量库/上传目录 + EMBEDDING_PROVIDER=hash（快速）+
无 DEEPSEEK_API_KEY（模板降级，确定性输出），不触碰真实数据。
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 必须在 import app 之前设置：完全隔离 + 确定性
os.environ["DATABASE_URL"] = "sqlite:///./test_p3.db"
os.environ["VECTOR_STORE_DIR"] = os.path.join(BASE_DIR, "vector_store_test_p3")
os.environ["KB_UPLOAD_DIR"] = os.path.join(BASE_DIR, "uploads_test_p3")
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["DEEPSEEK_API_KEY"] = ""

sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -- {detail}" if detail else ""))


def parse_sse(resp):
    """解析 SSE 流为 [(event, data_dict), ...]"""
    events, cur_event, data_lines = [], None, []
    for line in resp.text.splitlines():
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


def tool_seq(events):
    """提取 tool 事件序列：[(tool, ok), ...]"""
    return [
        (p["tool"], p.get("ok"))
        for k, p in events
        if k == "tool_result"
    ]


def route_of(events):
    for k, p in events:
        if k == "category":
            return p.get("route")
    return None


client = TestClient(app)


def run():
    # 准备用户 + 会话
    uname = f"p3user_{int(__import__('time').time())}"
    client.post("/register", json={"username": uname, "password": "test123456"})
    r = client.post("/login", data={"username": uname, "password": "test123456"})
    token = r.json().get("access_token", "")
    H = {"Authorization": f"Bearer {token}"}
    cid = client.post("/conversations", json={"title": "p3"}, headers=H).json()["id"]

    def chat(user_input, category="其他问题"):
        return parse_sse(client.post(
            "/chat", headers=H,
            json={"user_input": user_input, "conversation_id": cid, "category": category},
        ))

    # ---------- 1. 闲聊短路 ----------
    ev = chat("你好，在吗？")
    check("1.闲聊短路 normal_chat", route_of(ev) == "normal_chat"
          and not [k for k, _ in ev if k in ("rag", "tool_start", "tool_result")],
          f"route={route_of(ev)} events={[k for k, _ in ev]}")

    # ---------- 2. human_service ----------
    ev = chat("我要人工客服")
    reply = "".join(p.get("content", "") for k, p in ev if k == "message")
    check("2.human_service 固定文案不调 LLM",
          route_of(ev) == "human_service" and "人工客服" in reply
          and not [k for k, _ in ev if k in ("tool_start", "tool_result", "rag")],
          f"route={route_of(ev)} reply={reply[:20]}...")

    # ---------- 3. logistics_query 无订单号 ----------
    ev = chat("我的快递到哪里了？", "订单咨询")
    check("3.logistics_query 独立路由（缺订单号 ok=False）",
          route_of(ev) == "logistics_query" and tool_seq(ev) == [("logistics_query", False)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 4. logistics_query 带订单号 ----------
    ev = chat("包裹10001的物流信息", "订单咨询")
    check("4.logistics_query 命中（10001 ok=True）",
          route_of(ev) == "logistics_query" and tool_seq(ev) == [("logistics_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 5/6. fail-fast：不满足条件不接力 ----------
    ev = chat("订单10002到哪了？", "订单咨询")
    check("5.fail-fast 非「已发货」不查物流",
          route_of(ev) == "order_query" and tool_seq(ev) == [("order_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    ev = chat("帮我查订单10003，然后告诉我物流。", "订单咨询")
    check("6.fail-fast 已完成单不接力（10003 无在途物流）",
          route_of(ev) == "order_query" and tool_seq(ev) == [("order_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 7. Tool 失败终止 ----------
    ev = chat("订单99999现在什么状态？", "订单咨询")
    check("7.订单不存在 ok=False 链路终止",
          route_of(ev) == "order_query" and tool_seq(ev) == [("order_query", False)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 8. 多步链式 ----------
    ev = chat("帮我查一下订单10001，如果已经发货，再告诉我物流到哪里了。", "订单咨询")
    check("8.多步链式 order_query→logistics_query",
          route_of(ev) == "order_query"
          and tool_seq(ev) == [("order_query", True), ("logistics_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 9. 路由优先级（订单先于物流） ----------
    ev = chat("查一下订单10001的物流", "订单咨询")
    check("9.优先级 order_query 先行",
          route_of(ev) == "order_query"
          and tool_seq(ev) == [("order_query", True), ("logistics_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 10. P4.1 日志回归：已发货订单自动接力物流（P3.2 预期设计） ----------
    ev = chat("订单10001什么状态？", "订单咨询")
    check("10.P4.1 回归：已发货单自动接力 logistics",
          route_of(ev) == "order_query"
          and tool_seq(ev) == [("order_query", True), ("logistics_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 清理 ----------
    client.delete(f"/conversations/{cid}", headers=H)

    print()
    passed = sum(1 for _, ok in results if ok)
    print(f"===== 验收结果: {passed}/{len(results)} 通过 =====")
    for name, ok in results:
        if not ok:
            print(f"失败项: {name}")
    sys.exit(0 if passed == len(results) else 1)


run()
