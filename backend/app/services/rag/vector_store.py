"""VectorStore 抽象与轻量实现（P2.1）

设计：
- 业务代码只依赖 VectorStore 接口，不感知底层实现，后续可无缝替换
  Chroma / FAISS / Milvus（实现同名接口即可）；
- 第一版采用 JsonVectorStore：纯 Python 余弦检索 + JSON 文件持久化，
  每个知识库（collection）一个文件，零额外依赖；
- 未引入 Chroma 的原因：chromadb 的依赖树强制携带 fastapi/uvicorn/pydantic，
  会升级当前锁定的 fastapi 0.95.2 + pydantic 1.10.7，违反"保留现有功能"约束。
"""
import json
import os
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.core.config import VECTOR_STORE_DIR


class VectorStore(ABC):
    """向量存储抽象接口"""

    @abstractmethod
    def upsert(self, collection: str, ids: List[str], vectors: List[List[float]],
               metadatas: List[dict], documents: List[str]) -> None:
        """写入/覆盖向量"""

    @abstractmethod
    def delete_where(self, collection: str, metadata_filter: dict) -> int:
        """按 metadata 精确匹配删除，返回删除条数"""

    @abstractmethod
    def delete_collection(self, collection: str) -> None:
        """删除整个 collection"""

    @abstractmethod
    def query(self, collection: str, vector: List[float], top_k: int,
              metadata_filter: Optional[dict] = None) -> List[dict]:
        """余弦相似度检索，返回 [{id, score, metadata, document}]，按 score 降序"""

    @abstractmethod
    def count(self, collection: str) -> int:
        """collection 内向量条数"""


class JsonVectorStore(VectorStore):
    """JSON 文件持久化的轻量向量存储（collection 粒度读写锁 + 原子写入）"""

    def __init__(self, base_dir: str = VECTOR_STORE_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _path(self, collection: str) -> str:
        safe = "".join(c for c in collection if c.isalnum() or c in "_-")
        return os.path.join(self.base_dir, f"{safe}.json")

    def _lock(self, collection: str) -> threading.Lock:
        with self._global_lock:
            if collection not in self._locks:
                self._locks[collection] = threading.Lock()
            return self._locks[collection]

    def _load(self, collection: str) -> dict:
        path = self._path(collection)
        if not os.path.exists(path):
            return {"items": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # P5.1 P1-2：文件损坏时返回空，避免 JSONDecodeError 向上传播导致 /chat 500
            import logging as _logging
            _logging.getLogger("vector_store").warning(
                "vector store load failed collection=%s: %s", collection, e
            )
            return {"items": []}

    def _save(self, collection: str, data: dict) -> None:
        path = self._path(collection)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)  # 原子替换，避免半写文件

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def upsert(self, collection, ids, vectors, metadatas, documents) -> None:
        if not ids:
            return
        with self._lock(collection):
            data = self._load(collection)
            items = {item["id"]: item for item in data["items"]}
            for i, cid in enumerate(ids):
                items[cid] = {
                    "id": cid,
                    "vector": vectors[i],
                    "metadata": metadatas[i],
                    "document": documents[i],
                }
            data["items"] = list(items.values())
            self._save(collection, data)

    def delete_where(self, collection, metadata_filter) -> int:
        with self._lock(collection):
            data = self._load(collection)
            kept, removed = [], 0
            for item in data["items"]:
                if all(item["metadata"].get(k) == v for k, v in metadata_filter.items()):
                    removed += 1
                else:
                    kept.append(item)
            if removed:
                data["items"] = kept
                self._save(collection, data)
            return removed

    def delete_collection(self, collection) -> None:
        with self._lock(collection):
            path = self._path(collection)
            if os.path.exists(path):
                os.remove(path)

    def query(self, collection, vector, top_k, metadata_filter=None) -> List[dict]:
        with self._lock(collection):
            data = self._load(collection)
            results = []
            for item in data["items"]:
                if metadata_filter and not all(
                    item["metadata"].get(k) == v for k, v in metadata_filter.items()
                ):
                    continue
                results.append(
                    {
                        "id": item["id"],
                        "score": self._cosine(vector, item["vector"]),
                        "metadata": item["metadata"],
                        "document": item["document"],
                    }
                )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def count(self, collection) -> int:
        with self._lock(collection):
            return len(self._load(collection)["items"])


_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取全局 VectorStore 实例（业务代码统一入口，便于替换实现）"""
    global _store
    if _store is None:
        _store = JsonVectorStore()
    return _store


def reset_vector_store() -> None:
    """测试用：清空单例"""
    global _store
    _store = None
