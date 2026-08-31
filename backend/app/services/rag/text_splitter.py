"""文本清洗与 Chunk 切分（P2.1）

参数通过 core.config 管理（CHUNK_SIZE / CHUNK_OVERLAP），不写死在业务代码中。
"""
import re
from typing import List

from app.core.config import CHUNK_OVERLAP, CHUNK_SIZE

# 用于在块边界附近回退寻找自然断点的标点（优先长句末标点）
_BREAK_PUNCT = ["。", "！", "？", "；", "!", "?", ";", "\n", "，", ","]


def clean_text(text: str) -> str:
    """
    文本清洗：
    - 统一换行（PDF 常见 \\r\\n / \\r）
    - 全角空格转普通空格
    - 行尾空白去除；行内多空格压缩
    - 3 个以上连续换行压缩为 1 个空行（保留段落结构）
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line != "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    滑动窗口切分：
    - 单块上限 chunk_size 字符
    - 相邻块重叠 chunk_overlap 字符，保持上下文连续
    - 在窗口末尾附近回退到自然标点/换行处断开，避免句子被硬切
    - 过滤空白块
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max(chunk_size - chunk_overlap, 1)
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            window = text[start:end]
            # 从窗口尾部向前找自然断点（不低于窗口 40% 处，防止块过短）
            cut = -1
            for p in _BREAK_PUNCT:
                cut = window.rfind(p)
                if cut >= int(chunk_size * 0.4):
                    break
                cut = -1
            if cut != -1:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks
