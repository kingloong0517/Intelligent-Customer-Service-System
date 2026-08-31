"""Embedding 服务（P2.1/P2.2）

- 独立封装，业务代码只依赖 get_embedder()，不感知具体实现；
- LocalEmbedder：sentence-transformers 本地中文模型（BAAI/bge-small-zh-v1.5），
  无需 API Key，首次运行自动下载到本地缓存，之后完全离线加载；
- OpenAICompatEmbedder：OpenAI 兼容 /embeddings 协议（硅基流动、智谱、OpenAI 等），
  API Key / Base URL / 模型全部通过环境变量读取（core/config），不写死；
- HashEmbedder：零依赖的确定性本地降级（字符 3-gram feature hashing），
  作为 local/openai 均不可用时的最终 fallback；不具语义相似性。
"""
import hashlib
import logging
import os
import re
import time
from typing import List, Optional

import requests

# 国内网络直连 HuggingFace 常失败：首次下载模型默认走镜像（已缓存后无网络请求，
# 需要直连时可用环境变量覆盖 HF_ENDPOINT）。必须在此设置，早于 huggingface_hub 被导入。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from app.core.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_HASH_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    EMBEDDING_TIMEOUT,
)


class EmbeddingError(Exception):
    """Embedding 调用失败"""


class BaseEmbedder:
    name: str = "base"
    dim: int = 0

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class OpenAICompatEmbedder(BaseEmbedder):
    """OpenAI 兼容 /embeddings 协议实现"""

    # 智谱等部分服务对单次批量条数有上限，分批调用避免超限
    EMBED_BATCH_SIZE = 25
    # 限流（429）退避重试：间隔秒数
    RETRY_BACKOFF = (2, 5)

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.name = model
        self.dim = 0  # 首次调用后确定

    def _request_batch(self, batch: List[str]) -> List[List[float]]:
        """单批请求，429 限流时按退避间隔重试"""
        last_exc: Exception = None
        for attempt in range(len(self.RETRY_BACKOFF) + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": batch},
                    timeout=self.timeout,
                )
                if resp.status_code == 429:
                    # 智谱错误码 1113：余额不足/无资源包，确定性错误，重试无意义
                    try:
                        err = resp.json().get("error", {})
                    except Exception:
                        err = {}
                    if err.get("code") == "1113":
                        raise EmbeddingError(
                            f"Embedding 服务余额不足: {err.get('message', resp.text[:200])}"
                        )
                    if attempt < len(self.RETRY_BACKOFF):
                        time.sleep(self.RETRY_BACKOFF[attempt])
                        continue
                resp.raise_for_status()
                data = resp.json().get("data", [])
                if len(data) != len(batch):
                    raise EmbeddingError(
                        f"Embedding 返回条数不匹配: 期望 {len(batch)}, 实际 {len(data)}"
                    )
                # OpenAI 兼容协议标准字段为 embedding（智谱/硅基流动等），
                # 部分服务返回 vector，二者兼容
                result = []
                for item in data:
                    vec = item.get("embedding") or item.get("vector")
                    if not vec:
                        raise EmbeddingError("Embedding 响应缺少 embedding/vector 字段")
                    result.append(vec)
                return result
            except EmbeddingError:
                raise
            except Exception as e:
                last_exc = e
                if attempt < len(self.RETRY_BACKOFF):
                    time.sleep(self.RETRY_BACKOFF[attempt])
                    continue
        raise EmbeddingError(
            f"Embedding API 调用失败: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors: List[List[float]] = []
        for start in range(0, len(texts), self.EMBED_BATCH_SIZE):
            batch = texts[start : start + self.EMBED_BATCH_SIZE]
            vectors.extend(self._request_batch(batch))
        self.dim = len(vectors[0])
        return vectors


def _model_cached(model_name: str) -> bool:
    """检查 HF 缓存中是否已存在该模型（纯文件系统检查，不触发网络/import hf 库）"""
    hub = os.path.expanduser(os.environ.get("HF_HUB_CACHE", "~/.cache/huggingface/hub"))
    snap = os.path.join(hub, "models--" + model_name.replace("/", "--"), "snapshots")
    if not os.path.isdir(snap):
        return False
    for entry in os.listdir(snap):
        d = os.path.join(snap, entry)
        if os.path.isdir(d):
            files = os.listdir(d)
            if "config.json" in files and any(
                f.endswith((".safetensors", ".bin")) for f in files
            ):
                return True
    return False


class LocalEmbedder(BaseEmbedder):
    """sentence-transformers 本地中文模型（默认 BAAI/bge-small-zh-v1.5）

    - 首次运行自动下载模型到本地缓存（HF 缓存目录），之后完全离线加载；
    - 已缓存时设置 HF_HUB_OFFLINE=1：跳过远端校验，加载更快更稳定
      （必须早于 transformers/huggingface_hub 导入，二者在 import 时读取该变量）；
    - 无需任何 API Key；
    - 输出已做 L2 归一化，与现有 cosine similarity 检索逻辑完全兼容；
    - 文档 Chunk 与用户 Query 走同一实例同一模型，保证向量空间一致。
    """

    def __init__(self, model_name: str):
        if _model_cached(model_name):
            os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise EmbeddingError(
                "未安装 sentence-transformers，无法使用 EMBEDDING_PROVIDER=local"
            ) from e
        self.name = f"local:{model_name}"
        # 首次调用从 HF（镜像）下载，之后直接读本地缓存
        self.model = SentenceTransformer(model_name)
        # 新版改名 get_embedding_dimension，兼容旧版方法名
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,  # L2 归一化：cosine = dot，兼容现有检索
            batch_size=32,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


class HashEmbedder(BaseEmbedder):
    """确定性哈希降级：字符 3-gram feature hashing + L2 归一化（无语义，仅保证管线可用）"""

    def __init__(self, dim: int = EMBEDDING_HASH_DIM):
        self.dim = dim
        self.name = f"hash-3gram-{dim}"

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            tokens = re.sub(r"\s+", "", text or "")
            for i in range(len(tokens) - 2):
                gram = tokens[i : i + 3]
                h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:16], 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 16) & 1 else -1.0
                vec[idx] += sign
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


_embedder: Optional[BaseEmbedder] = None


def _make_local_or_hash() -> BaseEmbedder:
    """创建本地模型 embedder；加载失败（未安装/下载失败）时降级 hash（最终 fallback）"""
    try:
        return LocalEmbedder(EMBEDDING_MODEL)
    except Exception as e:
        logging.getLogger("embedder").warning(
            "local model %s load failed, fallback to hash: %s", EMBEDDING_MODEL, e
        )
        return HashEmbedder()


def get_embedder() -> BaseEmbedder:
    """按配置返回 Embedding 实例（进程内单例）"""
    global _embedder
    if _embedder is None:
        provider = (EMBEDDING_PROVIDER or "auto").lower()
        if provider == "hash":
            _embedder = HashEmbedder()
        elif provider == "local":
            _embedder = _make_local_or_hash()
        elif provider == "openai":
            if not EMBEDDING_API_KEY:
                raise EmbeddingError("EMBEDDING_PROVIDER=openai 但未配置 EMBEDDING_API_KEY")
            _embedder = OpenAICompatEmbedder(
                EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL, EMBEDDING_TIMEOUT
            )
        else:  # auto
            if EMBEDDING_API_KEY:
                _embedder = OpenAICompatEmbedder(
                    EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL, EMBEDDING_TIMEOUT
                )
            else:
                _embedder = _make_local_or_hash()
    return _embedder


def reset_embedder() -> None:
    """测试用：清空单例，使配置重新生效"""
    global _embedder
    _embedder = None
