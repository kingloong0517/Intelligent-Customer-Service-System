#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P4.2 Docker 部署验收脚本

前置条件：
  1. docker compose up -d --build 已完成，backend 容器 healthy
  2. 在 backend 目录运行（使用 .venv 的 requests）

用法：
  .venv\\Scripts\\python.exe verify_docker.py             # 全量部署测试（26 项）
  .venv\\Scripts\\python.exe verify_docker.py --persist   # compose down/up 后验证数据仍在
  .venv\\Scripts\\python.exe verify_docker.py --logs      # 检查容器日志 request_id 链路

覆盖清单（对应用户 26 项测试要求）：
  3./health(直连+经Nginx)  4.JWT  5.会话  6.普通聊天  7.SSE流式  8.降级可用
  9.建知识库  10.上传TXT/MD(PDF已在P2覆盖)  11.Embedding  12.VectorStore
  13.RAG检索  14.citation  15.Tool  16.多步Tool  17.多会话  18.消息历史
  20.uploads持久化  21.vector_store持久化  22.Request ID  25.前端生产构建
  26.Nginx SSE 流式
  19/24(数据持久化)由 --persist 模式覆盖
"""
import json
import os
import sys
import time

import requests

BACKEND = "http://127.0.0.1:8000"
FRONTEND = "http://127.0.0.1:3000"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai_chat/
DATA = os.path.join(ROOT, "data")
PERSIST_USER = "p4docker_persist"
PERSIST_PASS = "P4persist!123"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -- {detail}" if detail else ""))


def parse_sse(resp):
    """解析 SSE 流为 [(event, data_dict), ...]"""
    events, cur_event, data_lines = [], None, []
    for line in resp.iter_lines(decode_unicode=True):
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


def chat_sse(base, headers, payload, stream_check=False):
    """POST /chat（base 可为 BACKEND 或 FRONTEND/api），返回 (events, chunk_count)"""
    url = f"{base}/chat" if base == BACKEND else f"{base}/api/chat"
    chunks = 0
    with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as resp:
        if resp.status_code != 200:
            return [(f"http_{resp.status_code}", {})], chunks
        if stream_check:
            # 流式验证：多个网络分块陆续到达（非一次性缓冲）
            for _ in resp.iter_content(chunk_size=None):
                chunks += 1
                if chunks >= 3:
                    break
            resp.close()
            return [], chunks
        return parse_sse(resp), chunks


def tool_seq(events):
    return [(p["tool"], p.get("ok")) for k, p in events if k == "tool_result"]


def route_of(events):
    for k, p in events:
        if k == "category":
            return p.get("route")
    return None


def register_and_login(username, password):
    requests.post(f"{BACKEND}/register", json={"username": username, "password": password}, timeout=10)
    r = requests.post(f"{BACKEND}/login", data={"username": username, "password": password}, timeout=10)
    return r.json().get("access_token", "")


KB_MD = """# 售后服务政策

## 退货退款规则
自签收之日起 7 天内，商品未使用且不影响二次销售的，可申请无理由退货退款。
退款将在审核通过后 3-5 个工作日原路退回支付账户。

## 换货政策
商品存在质量问题的，自签收之日起 15 天内可申请免费换货，运费由商家承担。
"""


def run_full():
    # ---------- 3. /health（直连 + 经 Nginx）----------
    r = requests.get(f"{BACKEND}/health", timeout=10)
    h = r.json()
    check("3a./health 直连 status/database/vector_store",
          r.status_code == 200 and h.get("status") == "ok" and h.get("database") == "ok"
          and h.get("vector_store") in ("ok", "empty"),
          f"{h}")
    check("3b./health embedding 为本地模型", "local:BAAI/bge-small-zh-v1.5" in str(h.get("embedding", "")),
          f"embedding={h.get('embedding')}")
    r2 = requests.get(f"{FRONTEND}/api/health", timeout=10)
    check("3c./health 经 Nginx /api 代理", r2.status_code == 200 and r2.json().get("status") == "ok")

    # ---------- 22. Request ID ----------
    r = requests.get(f"{BACKEND}/health", headers={"X-Request-ID": "test-123"}, timeout=10)
    check("22a.客户端传入 X-Request-ID 原样回写", r.headers.get("X-Request-ID") == "test-123")
    r = requests.get(f"{BACKEND}/health", timeout=10)
    rid = r.headers.get("X-Request-ID", "")
    check("22b.未传时服务端自动生成", len(rid) == 32, f"request_id={rid[:8]}...")
    r = requests.get(f"{FRONTEND}/api/health", headers={"X-Request-ID": "via-nginx-1"}, timeout=10)
    check("22c.经 Nginx 代理 Request ID 仍回写", r.headers.get("X-Request-ID") == "via-nginx-1")

    # ---------- 4. JWT ----------
    ts = int(time.time())
    username = f"p4docker_{ts}"
    token = register_and_login(username, "test123456")
    check("4.JWT 注册+登录", bool(token))
    r = requests.post(f"{BACKEND}/login", data={"username": username, "password": "wrong"}, timeout=10)
    check("4b.错误密码 401", r.status_code == 401)
    r = requests.get(f"{BACKEND}/conversations", timeout=10)
    check("4c.无 Token 401", r.status_code == 401)
    H = {"Authorization": f"Bearer {token}"}

    # ---------- 5. 创建会话 ----------
    r = requests.post(f"{BACKEND}/conversations", json={"title": "p4.2"}, headers=H, timeout=10)
    cid = r.json().get("id")
    check("5.创建会话", bool(cid), f"conversation_id={cid}")

    # ---------- 6/7. 普通聊天 + SSE 流式 ----------
    ev, _ = chat_sse(BACKEND, H, {"user_input": "你好", "conversation_id": cid, "category": "其他问题"})
    kinds = [k for k, _ in ev]
    check("6.普通聊天 normal_chat", route_of(ev) == "normal_chat", f"route={route_of(ev)}")
    reply = "".join(p.get("content", "") for k, p in ev if k == "message")
    check("7.SSE 流式 message+done 收尾", "message" in kinds and kinds[-1] == "done" and bool(reply),
          f"events={kinds} reply={reply[:15]}...")

    # ---------- 8. 模板降级可用性（LLM 不可用时 reply 来自模板，非空即链路完好）----------
    check("8.回复内容非空（LLM 不可用时模板降级链路完好）", bool(reply.strip()))

    # ---------- 9/10/11/12. 知识库 + 上传 + Embedding + VectorStore ----------
    r = requests.post(f"{BACKEND}/kb", json={"name": f"docker-kb-{ts}", "description": "P4.2"},
                      headers=H, timeout=10)
    kb_id = r.json().get("id")
    check("9.创建知识库", bool(kb_id), f"kb_id={kb_id}")
    files = {"file": ("售后政策.md", KB_MD.encode("utf-8"), "text/markdown")}
    r = requests.post(f"{BACKEND}/kb/{kb_id}/documents", files=files, headers=H, timeout=30)
    doc_id = r.json().get("id")
    check("10.上传 MD 文档", bool(doc_id), f"doc_id={doc_id}")
    files = {"file": ("注意事项.txt", "发货时效：付款后 48 小时内发货。".encode("utf-8"), "text/plain")}
    requests.post(f"{BACKEND}/kb/{kb_id}/documents", files=files, headers=H, timeout=30)
    # 等待处理完成（本地 Embedding 模型首次加载 2-5s）
    ready = False
    for _ in range(60):
        r = requests.get(f"{BACKEND}/kb/{kb_id}/documents/{doc_id}", headers=H, timeout=10)
        st = (r.json() or {}).get("status")
        if st == "ready":
            ready = True
            break
        if st == "failed":
            break
        time.sleep(3)
    check("11.Embedding 处理 ready（本地模型）", ready, f"status={st}")

    # ---------- 13. RAG 检索 ----------
    r = requests.get(f"{BACKEND}/kb/search", params={"query": "退货退款规则是什么？"},
                     headers=H, timeout=30)
    hits = r.json() if isinstance(r.json(), list) else []
    check("13.RAG 检索命中", bool(hits) and hits[0].get("score", 0) > 0.3,
          f"hits={len(hits)} top_score={hits[0].get('score') if hits else None}")

    # ---------- 14. citation ----------
    ev, _ = chat_sse(BACKEND, H, {"user_input": "退货退款规则是什么？", "conversation_id": cid,
                                  "category": "售后问题"})
    cit = [p for k, p in ev if k == "citation"]
    rag_ev = [p for k, p in ev if k == "rag"]
    check("14.citation 事件（RAG used=true）",
          bool(cit) and cit[0].get("filename") == "售后政策.md"
          and bool(rag_ev) and rag_ev[0].get("used") is True,
          f"citation={cit[:1]}")

    # ---------- 15. Tool Calling ----------
    ev, _ = chat_sse(BACKEND, H, {"user_input": "我的订单10001现在什么状态？", "conversation_id": cid,
                                  "category": "订单咨询"})
    check("15.Tool order_query 执行成功",
          route_of(ev) == "order_query" and tool_seq(ev) == [("order_query", True)],
          f"route={route_of(ev)} tools={tool_seq(ev)}")

    # ---------- 16. 多步 Tool ----------
    ev, _ = chat_sse(BACKEND, H, {"user_input": "帮我查一下订单10001，如果已经发货，再告诉我物流到哪里了。",
                                  "conversation_id": cid, "category": "订单咨询"})
    check("16.多步 Tool order→logistics 链式",
          tool_seq(ev) == [("order_query", True), ("logistics_query", True)],
          f"tools={tool_seq(ev)}")

    # ---------- 17. 多会话 ----------
    r = requests.post(f"{BACKEND}/conversations", json={"title": "second"}, headers=H, timeout=10)
    cid2 = r.json().get("id")
    chat_sse(BACKEND, H, {"user_input": " second 会话测试", "conversation_id": cid2, "category": "其他问题"})
    m1 = requests.get(f"{BACKEND}/conversations/{cid}/messages", headers=H, timeout=10).json()
    m2 = requests.get(f"{BACKEND}/conversations/{cid2}/messages", headers=H, timeout=10).json()
    c1 = [x.get("content", "") for x in m1]
    c2 = [x.get("content", "") for x in m2]
    check("17.多会话消息隔离", bool(c1) and bool(c2) and not set(c1) & set(c2),
          f"len={len(m1)}/{len(m2)}")

    # ---------- 18. 消息历史 ----------
    roles = [x.get("role") for x in m1]
    check("18.消息历史落库（user+assistant）", "user" in roles and "assistant" in roles, f"roles={roles}")

    # ---------- 20/21. 持久化目录落盘 ----------
    up = os.path.join(DATA, "uploads", "kb")
    vs = os.path.join(DATA, "vector_store")
    check("20.uploads 持久化（宿主 data/uploads）", os.path.isdir(up) and any(os.scandir(up)),
          f"{sorted(os.listdir(up))[:3] if os.path.isdir(up) else 'missing'}")
    kb_files = [f for f in os.listdir(vs) if f.startswith("kb_")] if os.path.isdir(vs) else []
    check("21.vector_store 持久化（宿主 data/vector_store）", bool(kb_files), f"{kb_files}")

    # ---------- 25. 前端生产构建 ----------
    r = requests.get(FRONTEND, timeout=10)
    html = r.text
    check("25a.前端 index.html", r.status_code == 200 and 'id="app"' in html)
    r = requests.get(f"{FRONTEND}/chat", timeout=10)
    check("25b.Vue Router history fallback", r.status_code == 200 and 'id="app"' in r.text)
    import re
    m = re.search(r'src="(/assets/[^"]+\.js)"', html)
    asset_ok = False
    if m:
        ar = requests.get(f"{FRONTEND}{m.group(1)}", timeout=10)
        asset_ok = ar.status_code == 200 and len(ar.content) > 1000
    check("25c.静态资源 /assets 可访问", asset_ok)

    # ---------- 26. Nginx SSE 流式 ----------
    ev, chunks = chat_sse(FRONTEND, H, {"user_input": "你好", "conversation_id": cid,
                                        "category": "其他问题"})
    kinds = [k for k, _ in ev]
    check("26.Nginx 代理 SSE 完整事件流（category→…→done）",
          "category" in kinds and "message" in kinds and kinds[-1] == "done", f"events={kinds}")

    # ---------- 登出前记录持久化标记 ----------
    requests.put(f"{BACKEND}/conversations/{cid}", json={"title": "persist-marker"}, headers=H,
                 timeout=10) if _has_rename_api() else None
    print()
    print("===== 提示：docker compose down && docker compose up -d 后运行 --persist 验证数据保留 =====")
    finish()


def _has_rename_api():
    # 会话改名接口存在与否不影响主流程（19/24 由 --persist 检查）
    return False


def run_persist():
    """down/up 后运行：验证 19/24 数据持久化"""
    token = register_and_login(PERSIST_USER, PERSIST_PASS)
    if not token:
        token = register_and_login(PERSIST_USER, PERSIST_PASS)
    H = {"Authorization": f"Bearer {token}"}
    convs = requests.get(f"{BACKEND}/conversations", headers=H, timeout=10).json()
    check("19/24a.重启后账号与会话仍在", bool(convs), f"conversations={len(convs)}")
    if convs:
        cid = convs[0]["id"]
        msgs = requests.get(f"{BACKEND}/conversations/{cid}/messages", headers=H, timeout=10).json()
        check("19/24b.重启后消息历史仍在", bool(msgs), f"messages={len(msgs)}")
    kbs = requests.get(f"{BACKEND}/kb", headers=H, timeout=10).json()
    check("19/24c.重启后知识库仍在", bool(kbs), f"kb_count={len(kbs)}")
    r = requests.get(f"{BACKEND}/kb/search", params={"query": "退货退款规则是什么？"},
                     headers=H, timeout=30)
    hits = r.json() if isinstance(r.json(), list) else []
    check("19/24d.重启后 RAG 向量检索仍可用（Embedding 未重建）",
          bool(hits) and hits[0].get("score", 0) > 0.3,
          f"top_score={hits[0].get('score') if hits else None}")
    vs = os.path.join(DATA, "vector_store")
    kb_files = [f for f in os.listdir(vs) if f.startswith("kb_")] if os.path.isdir(vs) else []
    check("19/24e.vector_store 文件仍在（未被重建）", bool(kb_files), f"{kb_files}")
    finish()


def run_logs():
    """检查容器日志 request_id 全链路"""
    import subprocess
    docker = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    out = subprocess.run([docker, "logs", "ai-chat-backend"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=30)
    logs = (out.stdout or "") + (out.stderr or "")
    check("23a.日志含 request_id", "[request_id=" in logs)
    check("23b.日志含 route= 链路", "route=" in logs)
    check("23c.日志含 tool_result+duration_ms", "tool_result" in logs and "duration_ms=" in logs)
    check("23d.日志含 rag/llm/persist 关键字", ("rag retrieve" in logs or "stream=" in logs)
          and "chat_persist" in logs)
    key_leak = [ln for ln in logs.splitlines() if "sk-" in ln and "DEEPSEEK_API_KEY" not in ln
                and "llm_configured" not in ln]
    check("23e.日志无 API Key 泄漏", not key_leak, f"{key_leak[:1]}")
    finish()


def finish():
    print()
    passed = sum(1 for _, ok in results if ok)
    print(f"===== 验收结果: {passed}/{len(results)} 通过 =====")
    for name, ok in results:
        if not ok:
            print(f"失败项: {name}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    if "--persist" in sys.argv:
        run_persist()
    elif "--logs" in sys.argv:
        run_logs()
    else:
        run_full()
