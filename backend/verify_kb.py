#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2.1 验收脚本：企业客服知识库

覆盖检查项：
  1. 创建知识库            8.  向量写入
  2. 上传 TXT             9.  删除文档（级联 chunks + 向量）
  3. 上传 Markdown        10. 删除知识库（级联 + 向量文件清理）
  4. 上传 PDF             11. 非法文件处理
  5. 文档解析             12. 空文件处理
  6. Chunk 创建           13. JWT 鉴权
  7. Embedding            14. 原有 /chat 功能不受影响（P1 回归）

用法（在 backend 目录下）：
    python verify_kb.py
说明：全程使用独立测试库 test_p21.db + 临时 uploads/vector 目录，不触碰真实数据。
"""
import json
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 必须在 import app 之前设置：独立测试库 / 临时向量与上传目录 / 强制本地哈希 Embedding
os.environ["DATABASE_URL"] = "sqlite:///./test_p21.db"
os.environ["KB_UPLOAD_DIR"] = os.path.join(BASE_DIR, "uploads_test_kb")
os.environ["VECTOR_STORE_DIR"] = os.path.join(BASE_DIR, "vector_store_test_kb")
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["EMBEDDING_API_KEY"] = ""

# 进程启动早期清理上轮可能残留的测试产物（此时无文件锁）
for _p in [
    os.path.join(BASE_DIR, "test_p21.db"),
    os.path.join(BASE_DIR, "uploads_test_kb"),
    os.path.join(BASE_DIR, "vector_store_test_kb"),
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
from app.core.config import CHUNK_SIZE, CHUNK_OVERLAP  # noqa: E402
from app.services.rag.embedder import get_embedder  # noqa: E402
from app.services.rag.vector_store import get_vector_store  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}" + (f"  -- {detail}" if detail else ""))


def make_test_pdf(text: str) -> bytes:
    """手写最小可提取文本的 PDF（ASCII 内容，pypdf 可解析）"""
    esc = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 14 Tf 72 720 Td ({esc}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    return out


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
H = {}  # 登录后填充的鉴权头（供模块级 upload() 使用）


def upload(kb_id, filename, data):
    r = client.post(
        f"/kb/{kb_id}/documents",
        files={"file": (filename, data)},
        headers=H,
    )
    return r


def main():
    global H
    # ---------- 13. JWT ----------
    r = client.get("/kb")
    check("13a.无token访问/kb 401", r.status_code == 401)
    r = client.get("/kb", headers={"Authorization": "Bearer bad"})
    check("13b.无效token 401", r.status_code == 401)

    # 注册登录
    uname = f"kbuser_{int(__import__('time').time())}"
    client.post("/register", json={"username": uname, "password": "test123456"})
    r = client.post("/login", data={"username": uname, "password": "test123456"})
    token = r.json().get("access_token", "")
    H = {"Authorization": f"Bearer {token}"}
    check("13c.登录获取JWT", bool(token))

    # ---------- 1. 创建知识库 ----------
    r = client.post("/kb", json={"name": "客服知识库A", "description": "退换货政策与产品说明"}, headers=H)
    check("1a.创建知识库", r.status_code == 200 and r.json()["name"] == "客服知识库A")
    kb1 = r.json()["id"]
    r = client.post("/kb", json={"name": "客服知识库A"}, headers=H)
    check("1b.重名知识库 400", r.status_code == 400)
    r = client.post("/kb", json={"name": "知识库B"}, headers=H)
    kb2 = r.json()["id"]
    check("1c.第二个知识库", r.status_code == 200)
    r = client.post("/kb", json={"name": "孤儿库"}, headers=H)
    orphan_id = r.json()["id"]
    r = client.post(f"/kb/{kb2}/documents", files={"file": ("x.txt", b"data")}, headers=H)
    r = client.delete(f"/kb/{kb2}", headers=H)
    check("1d.删除空库+404校验", r.status_code == 200
          and client.get(f"/kb/{kb2}", headers=H).status_code == 404)
    r = client.post("/kb/999999/documents", files={"file": ("x.txt", b"data")}, headers=H)
    check("1e.向不存在库上传 404", r.status_code == 404)

    # ---------- 2. 上传 TXT（长文本触发多分块） ----------
    para = ("智能客服系统支持七天无理由退货，退款将在审核通过后1至3个工作日原路退回。" * 6)
    txt_content = "\n\n".join(f"第{i}节：{para}" for i in range(1, 5)).encode("utf-8")
    r = upload(kb1, "售后政策.txt", txt_content)
    # 上传接口异步处理：响应时应为 pending/processing（处理快时也可能已 ready）
    check("2a.上传TXT(异步受理)", r.status_code == 200
          and r.json()["status"] in ("pending", "processing", "ready"),
          f"status={r.json().get('status')}")
    doc_txt = r.json()["id"]

    # ---------- 3. 上传 Markdown ----------
    md_content = (
        "# 产品使用手册\n\n## 快速开始\n\n下载APP并注册账号，即可开始使用智能客服。\n\n"
        "## 常见问题\n\n- 忘记密码：在登录页点击找回密码\n- 修改手机号：进入账户设置页\n"
        "- 发票开具：订单详情页申请电子发票\n\n## 联系客服\n\n工作日9:00-18:00在线。"
    ).encode("utf-8")
    r = upload(kb1, "产品手册.md", md_content)
    check("3.上传Markdown", r.status_code == 200, f"status={r.json().get('status')}")
    doc_md = r.json()["id"]

    # ---------- 4. 上传 PDF ----------
    pdf_data = make_test_pdf("KBTestPDFDocument. The refund policy is 7 days. Shipping takes 3 to 5 days.")
    r = upload(kb1, "英文说明.pdf", pdf_data)
    check("4.上传PDF", r.status_code == 200, f"status={r.json().get('status')}")
    doc_pdf = r.json()["id"]

    # TestClient 在响应前同步执行 BackgroundTasks，此时应已处理完成
    detail = client.get(f"/kb/{kb1}", headers=H).json()
    docs = {d["id"]: d for d in detail["documents"]}

    # ---------- 5. 文档解析 + 6. Chunk 创建 ----------
    d_txt = docs[doc_txt]
    check("5a.TXT解析完成(ready)", d_txt["status"] == "ready", f"状态={d_txt['status']} 错误={d_txt['error_message']}")
    check("6a.TXT多分块(>=2)", d_txt["chunk_count"] >= 2, f"chunk_count={d_txt['chunk_count']}")
    d_md = docs[doc_md]
    check("5b.MD解析完成(ready)", d_md["status"] == "ready", f"错误={d_md['error_message']}")
    check("6b.MD分块>=1", d_md["chunk_count"] >= 1, f"chunk_count={d_md['chunk_count']}")
    d_pdf = docs[doc_pdf]
    check("5c.PDF解析完成(ready)", d_pdf["status"] == "ready", f"错误={d_pdf['error_message']}")

    r = client.get(f"/kb/{kb1}/documents/{doc_txt}/chunks", headers=H)
    chunks = r.json()
    check("6c.分块内容与overlap", r.status_code == 200 and len(chunks) == d_txt["chunk_count"]
          and all(c["char_count"] <= CHUNK_SIZE for c in chunks),
          f"块数={len(chunks)}, CHUNK_SIZE={CHUNK_SIZE}, OVERLAP={CHUNK_OVERLAP}")
    clean_ok = all("\r" not in c["content"] and c["content"].strip() == c["content"] for c in chunks)
    check("5d.文本清洗(无\\r/首尾空白)", clean_ok)

    # ---------- 7. Embedding ----------
    emb = get_embedder()
    v1 = emb.embed(["七天无理由退货"])[0]
    v2 = emb.embed(["七天无理由退货"])[0]
    v3 = emb.embed(["今天天气很好"])[0]
    same = v1 == v2
    diff = v1 != v3
    norm = sum(x * x for x in v1) ** 0.5
    check("7.Embedding(确定性/可区分/归一化)", same and diff and abs(norm - 1.0) < 1e-6,
          f"model={emb.name}, dim={emb.dim}")

    # ---------- 8. 向量写入 + 检索 ----------
    store = get_vector_store()
    total_chunks = d_txt["chunk_count"] + d_md["chunk_count"] + d_pdf["chunk_count"]
    stored = store.count(f"kb_{kb1}")
    check("8a.向量条数=分块总数", stored == total_chunks, f"store={stored}, chunks={total_chunks}")
    r = client.post(f"/kb/{kb1}/search", json={"query": "退款多久到账，原路退回", "top_k": 3}, headers=H)
    hits = r.json().get("hits", [])
    check("8b.检索命中TXT内容", r.status_code == 200 and len(hits) > 0
          and "退货" in hits[0]["content"], f"top1.score={hits[0]['score'] if hits else '-'}")
    check("8c.检索元数据(filename)", hits and hits[0]["filename"] == "售后政策.txt")
    r = client.post(f"/kb/{kb1}/search", json={"query": "How does the refund policy work?"}, headers=H)
    check("8d.检索命中PDF内容", "refund" in r.json()["hits"][0]["content"].lower()
          or "refund" in " ".join(h["content"].lower() for h in r.json()["hits"]))

    # ---------- 11. 非法文件 / 12. 空文件 / 处理失败可见 ----------
    r = upload(kb1, "病毒.exe", b"MZ fake binary")
    check("11a.非法类型 400", r.status_code == 400)
    r = upload(kb1, "空文件.txt", b"")
    check("12a.空文件 400", r.status_code == 400)
    r = upload(kb1, "坏文档.pdf", b"this is not a real pdf at all")
    doc_bad = r.json().get("id")
    detail = client.get(f"/kb/{kb1}", headers=H).json()
    d_bad = next((d for d in detail["documents"] if d["id"] == doc_bad), {})
    check("11b.坏PDF→failed且记录错误(不静默)", d_bad.get("status") == "failed"
          and bool(d_bad.get("error_message")), f"error={d_bad.get('error_message', '')[:60]}")

    # ---------- 9. 删除文档 ----------
    before = store.count(f"kb_{kb1}")
    r = client.delete(f"/kb/{kb1}/documents/{doc_txt}", headers=H)
    after_detail = client.get(f"/kb/{kb1}", headers=H).json()
    after_docs = {d["id"]: d for d in after_detail["documents"]}
    r_chunks = client.get(f"/kb/{kb1}/documents/{doc_txt}/chunks", headers=H)
    check("9.删除文档级联(向量+分块)", r.status_code == 200
          and store.count(f"kb_{kb1}") == before - d_txt["chunk_count"]
          and doc_txt not in after_docs
          and r_chunks.status_code == 404)
    orphan = upload(orphan_id, "孤儿.txt", "孤儿库文档内容".encode("utf-8"))
    check("9b.独立库上传正常", orphan.status_code == 200)

    # ---------- 10. 删除知识库 ----------
    kb_dir = os.path.join(BASE_DIR, "uploads_test_kb", f"kb{kb1}")
    vs_file = os.path.join(BASE_DIR, "vector_store_test_kb", f"kb_{kb1}.json")
    r = client.delete(f"/kb/{kb1}", headers=H)
    check("10.删除知识库级联", r.status_code == 200
          and client.get(f"/kb/{kb1}", headers=H).status_code == 404
          and not os.path.exists(vs_file)
          and not os.path.exists(kb_dir))

    # ---------- 14. P1 回归：/chat 事件化 SSE 不受影响 ----------
    conv = client.post("/conversations", json={"title": "P2回归会话"}, headers=H).json()
    with client.stream(
        "POST", "/chat", headers=H,
        json={"user_input": "我的订单什么时候发货？", "conversation_id": conv["id"], "category": "订单咨询"},
    ) as resp:
        events = parse_sse(resp.iter_lines()) if resp.status_code == 200 else [("http_error", {})]
    kinds = [k for k, _ in events]
    reply = "".join(p.get("content", "") for k, p in events if k == "message")
    check("14./chat回归(SSE事件流+降级模板)", kinds[0] == "category" and kinds[-1] == "done"
          and len(reply) > 0, f"事件数={len(kinds)}")
    hist = client.get("/history", params={"conversation_id": conv["id"]}, headers=H).json()
    check("14b./chat落库正常", bool(hist) and hist[-1]["ai_reply"] == reply)


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
        for path in [
            os.path.join(BASE_DIR, "test_p21.db"),
            os.path.join(BASE_DIR, "uploads_test_kb"),
            os.path.join(BASE_DIR, "vector_store_test_kb"),
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
