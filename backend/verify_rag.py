#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2.2 验收脚本：RAG 正式接入 /chat

覆盖检查项：
  1. 知识库问题 → RAG 命中          8.  无 Embedding Key → hash fallback 正常运行
  2. 闲聊 → 不走 RAG               9.  DeepSeek 失败 → 模板降级（402 环境下真实触发）
  3. 高相似度 → 正常 RAG           10. 多会话
  4. 低相似度 → 不强行使用无关知识   11. JWT
  5. RAG + SSE（事件序列完整）      12. 历史消息落库（含 rag_used 标记）
  6. citation（真实来源）          13. P1 回归（本脚本 14c + 另跑 verify_p1.py）
  7. 中文 PDF（reportlab 生成）    14. P2.1 回归（另跑 verify_kb.py）

用法（在 backend 目录下）：
    python verify_rag.py
说明：独立测试库 test_p22.db + 临时目录；hash embedding 分数偏低，
      命中/低相似场景通过 patch RAG_SIMILARITY_THRESHOLD 分别驱动。
"""
import io
import json
import os
import shutil
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 必须在 import app 之前设置：独立测试库 / 临时目录 / hash embedding
os.environ["DATABASE_URL"] = "sqlite:///./test_p22.db"
os.environ["KB_UPLOAD_DIR"] = os.path.join(BASE_DIR, "uploads_test_rag")
os.environ["VECTOR_STORE_DIR"] = os.path.join(BASE_DIR, "vector_store_test_rag")
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["EMBEDDING_API_KEY"] = ""

# 启动早期清理上轮残留
for _p in [
    os.path.join(BASE_DIR, "test_p22.db"),
    os.path.join(BASE_DIR, "uploads_test_rag"),
    os.path.join(BASE_DIR, "vector_store_test_rag"),
]:
    if os.path.isdir(_p):
        shutil.rmtree(_p, ignore_errors=True)
    elif os.path.exists(_p):
        try:
            os.remove(_p)
        except OSError:
            pass

sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
import app.services.rag.rag_service as rag_svc  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -- {detail}" if detail else ""))


def make_chinese_pdf(lines):
    """reportlab + 系统黑体生成真实中文 PDF（嵌入 TTF 子集，pypdf 可提取）"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for line in lines:
        c.setFont("SimHei", 12)
        c.drawString(60, y, line)
        y -= 24
    c.save()
    return buf.getvalue()


def parse_sse(line_iter):
    events, cur, data_lines = [], None, []
    for line in line_iter:
        line = line.rstrip("\r")
        if line == "":
            if cur is not None or data_lines:
                payload = json.loads("\n".join(data_lines)) if data_lines else {}
                events.append((cur or "message", payload))
            cur, data_lines = None, []
        elif line.startswith("event:"):
            cur = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip(" "))
    if cur is not None or data_lines:
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((cur or "message", payload))
    return events


client = TestClient(app)
H = {}


def chat_sse(user_input, conversation_id, category):
    with client.stream(
        "POST", "/chat", headers=H,
        json={"user_input": user_input, "conversation_id": conversation_id, "category": category},
    ) as resp:
        if resp.status_code != 200:
            return [(f"http_{resp.status_code}", {})]
        return parse_sse(resp.iter_lines())


def upload(kb_id, filename, data):
    return client.post(f"/kb/{kb_id}/documents", files={"file": (filename, data)}, headers=H)


def main():
    global H
    # ---------- 11. JWT ----------
    check("11a.无token 401", client.get("/kb").status_code == 401)
    uname = f"raguser_{int(time.time())}"
    client.post("/register", json={"username": uname, "password": "test123456"})
    H = {"Authorization": f"Bearer {client.post('/login', data={'username': uname, 'password': 'test123456'}).json()['access_token']}"}
    check("11b.登录JWT", bool(H["Authorization"]))

    # ---------- 知识库数据准备（TXT + 中文 PDF） ----------
    r = client.post("/kb", json={"name": "客服知识库", "description": "P2.2 RAG 测试"}, headers=H)
    kb_id = r.json()["id"]

    txt = "\n\n".join([
        "退货政策：商品自签收之日起七天内支持无理由退货，需保持商品完好。",
        "退款说明：退货审核通过后，退款将在1至3个工作日内原路退回到付款账户。",
        "保修条款：自购买之日起提供一年免费保修，人为损坏不在保修范围内。",
        "换货服务：质量问题十五天内支持免费换货，运费由商家承担。",
    ])
    r = upload(kb_id, "售后政策.txt", txt.encode("utf-8"))
    check("准备:TXT上传ready", r.status_code == 200 and r.json()["status"] in ("pending", "ready"))

    pdf_lines = [
        "发票开具流程说明",
        "订单完成后，用户可以在订单详情页点击申请开票按钮申请电子发票。",
        "电子发票将在三个工作日内发送到您的注册邮箱。",
        "密码找回流程说明",
        "在登录页面点击忘记密码，通过注册手机号验证后即可重置密码。",
        "如手机号已停用，请联系人工客服进行身份核实后找回账户。",
    ]
    r = upload(kb_id, "发票与账户指南.pdf", make_chinese_pdf(pdf_lines))
    check("准备:中文PDF上传ready", r.status_code == 200 and r.json()["status"] in ("pending", "ready"))
    time.sleep(0.5)

    detail = client.get(f"/kb/{kb_id}", headers=H).json()
    docs = {d["filename"]: d for d in detail["documents"]}
    check("准备:两文档均ready", len(docs) == 2 and all(d["status"] == "ready" for d in docs.values()),
          str({k: v["status"] for k, v in docs.items()}))

    # ---------- 7. 中文 PDF：解析/Chunk 内容中文正常 ----------
    pdf_doc = docs["发票与账户指南.pdf"]
    chunks = client.get(f"/kb/{kb_id}/documents/{pdf_doc['id']}/chunks", headers=H).json()
    pdf_text = "".join(c["content"] for c in chunks)
    check("7a.中文PDF解析无乱码", "发票" in pdf_text and "密码" in pdf_text and "订单详情页" in pdf_text,
          f"chunk_count={len(chunks)}")

    # ---------- 2/3. should_use_rag 路由判断 ----------
    check("2a.闲聊不走RAG", rag_svc.should_use_rag("其他问题", "你好呀，今天天气不错") is False)
    check("2b.笑话不走RAG", rag_svc.should_use_rag("其他问题", "给我讲个笑话") is False)
    check("3a.售后分类走RAG", rag_svc.should_use_rag("售后问题", "退款多久到账") is True)
    check("3b.无分类但含知识关键词走RAG", rag_svc.should_use_rag("其他问题", "发票怎么申请") is True)

    # ---------- 多会话准备 ----------
    conv1 = client.post("/conversations", json={"title": "RAG会话一"}, headers=H).json()["id"]
    conv2 = client.post("/conversations", json={"title": "RAG会话二"}, headers=H).json()["id"]
    check("10.多会话创建", conv1 != conv2)

    # ---------- 1/3/5/6. RAG 命中：TXT 检索 + SSE 完整事件 + citation ----------
    rag_svc.RAG_SIMILARITY_THRESHOLD = 0.01  # hash 降级分数低，压低阈值驱动命中路径
    events = chat_sse("七天无理由退货怎么办理？退款多久能到账？", conv1, "售后问题")
    kinds = [k for k, _ in events]
    rag_ev = next((p for k, p in events if k == "rag"), None)
    citations = [p for k, p in events if k == "citation"]
    reply = "".join(p.get("content", "") for k, p in events if k == "message")
    check("1.RAG命中(rag事件used=true)", rag_ev is not None and rag_ev["used"] is True
          and rag_ev["reason"] == "ok", f"reason={rag_ev and rag_ev['reason']} top={rag_ev and rag_ev['top_score']}")
    check("5.SSE事件序列完整", kinds[0] == "category" and "rag" in kinds and kinds[-1] == "done"
          and kinds.index("citation") < kinds.index("message"), str(kinds[:6]))
    check("6a.citation真实来源(filename)", len(citations) > 0
          and all(c["filename"] in ("售后政策.txt", "发票与账户指南.pdf") for c in citations)
          and all(isinstance(c["chunk_index"], int) and bool(c["chunk_key"]) for c in citations),
          f"citations={[(c['filename'], c['chunk_index']) for c in citations][:3]}")
    check("6b.citation与检索内容一致", any("退货" in c["snippet"] or "退款" in c["snippet"] for c in citations))

    # ---------- 12. 落库（含 rag_used） ----------
    hist = client.get("/history", params={"conversation_id": conv1}, headers=H).json()
    m = hist[-1] if hist else {}
    check("12.落库+rag_used=true", m.get("rag_used") is True and m.get("ai_reply") == reply
          and m.get("user_input") == "七天无理由退货怎么办理？退款多久能到账？")

    # ---------- 7b. 中文 PDF 检索命中（RAG 全链路到 citation） ----------
    events = chat_sse("电子发票在哪里申请开具？", conv2, "产品咨询")
    citations = [p for k, p in events if k == "citation"]
    rag_ev = next((p for k, p in events if k == "rag"), None)
    check("7b.中文PDF经RAG命中并出citation", rag_ev and rag_ev["used"] and len(citations) > 0
          and citations[0]["filename"] == "发票与账户指南.pdf"
          and any("发票" in c["snippet"] for c in citations),
          f"citations={[(c['filename'], c['chunk_index']) for c in citations][:2]}")

    # ---------- 2c. 闲聊端到端：不产生 rag/citation 事件 ----------
    events = chat_sse("你好呀，在吗？", conv1, "其他问题")
    kinds = [k for k, _ in events]
    check("2c.闲聊端到端无rag/citation", "rag" not in kinds and "citation" not in kinds
          and kinds[0] == "category" and kinds[-1] == "done", str(kinds[:4]))
    hist = client.get("/history", params={"conversation_id": conv1}, headers=H).json()
    check("2d.闲聊落库rag_used=false", hist[-1]["rag_used"] is False)

    # ---------- 4. 低相似度：不强行使用无关知识 ----------
    # 含"退货"关键词确保路由进入 RAG，但语义与知识库无关，高阈值下走 low_similarity
    rag_svc.RAG_SIMILARITY_THRESHOLD = 0.99  # 极高阈值驱动 low_similarity 路径
    events = chat_sse("量子力学的退货政策具体是什么？", conv2, "其他问题")
    rag_ev = next((p for k, p in events if k == "rag"), None)
    kinds = [k for k, _ in events]
    check("4.低相似→used=false且无citation", rag_ev is not None and rag_ev["used"] is False
          and rag_ev["reason"] == "low_similarity" and "citation" not in kinds and kinds[-1] == "done",
          f"reason={rag_ev and rag_ev['reason']}")

    # ---------- 8. hash fallback（全程 EMBEDDING_PROVIDER=hash 已在运行）+ 9. 降级 ----------
    # 当前环境无 EMBEDDING_API_KEY：embedding 走 hash，DeepSeek 因 402 余额不足走模板降级
    # hash 向量对短查询相似度可能为负分，阈值取 -1.0 保证驱动 used=True 命中路径
    rag_svc.RAG_SIMILARITY_THRESHOLD = -1.0
    events = chat_sse("保修期是多久？", conv2, "售后问题")
    rag_ev = next((p for k, p in events if k == "rag"), None)
    reply = "".join(p.get("content", "") for k, p in events if k == "message")
    all_templates = {t for v in __import__("app.services.chat_service", fromlist=["x"]).CATEGORY_RESPONSES.values() for t in v}
    check("8.hash fallback全链路可用", rag_ev and rag_ev["embedding_model"].startswith("hash")
          and rag_ev["used"] is True)
    check("9.LLM失败→模板降级(done收尾)", reply in all_templates and events[-1][0] == "done",
          f"reply={reply[:20]}")

    # ---------- 13. P1 回归（脚本内快速链路） ----------
    check("13./chat落库与统计正常",
          client.get("/conversations", headers=H).json()[0]["message_count"] >= 1)

    # 恢复默认阈值
    rag_svc.RAG_SIMILARITY_THRESHOLD = __import__("app.core.config", fromlist=["x"]).RAG_SIMILARITY_THRESHOLD


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
        for path in [
            os.path.join(BASE_DIR, "test_p22.db"),
            os.path.join(BASE_DIR, "uploads_test_rag"),
            os.path.join(BASE_DIR, "vector_store_test_rag"),
        ]:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    failed = [n for n, ok in results if not ok]
    print(f"\n===== 验收结果: {len(results) - len(failed)}/{len(results)} 通过 =====")
    if failed:
        print("失败项: " + "; ".join(failed))
        sys.exit(1)
    print("全部通过")
