"""向量后端工厂：按配置选择 Chroma 或 Qdrant，并提供兼容单例。

默认使用 Qdrant（本机已部署 http://localhost:6333），可通过环境变量
VECTOR_BACKEND=chroma 切换回 Chroma 本地持久化模式。
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from app.config import Config
from app.services.vector_stores.contracts import DEFAULT_COLLECTION_NAME

logger = logging.getLogger(__name__)

_backend_singleton: Any = None
_vector_store_singleton: Any = None


def _get(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def create_vector_backend(
    *,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    settings: Optional[Mapping[str, Any]] = None,
    dimension: Optional[int] = None,
) -> Any:
    """按配置创建向量后端实例。

    settings 可为 Config 类或 dict，支持键：
    VECTOR_BACKEND（chroma|qdrant）、CHROMA_PERSIST_DIRECTORY、
    QDRANT_URL、QDRANT_PATH。
    dimension 仅供 Qdrant 首次建 collection 时显式指定（默认懒取 embedding 维度）。
    """
    source = settings if settings is not None else Config
    backend_name = str(_get(source, "VECTOR_BACKEND", "qdrant")).strip().lower()
    if backend_name not in ("chroma", "qdrant"):
        logger.warning("未知向量后端 %r，回退到 qdrant", backend_name)
        backend_name = "qdrant"

    if backend_name == "qdrant":
        from app.services.vector_stores.qdrant import QdrantVectorBackend

        return QdrantVectorBackend(
            collection_name=collection_name,
            url=str(_get(source, "QDRANT_URL", "") or ""),
            path=str(_get(source, "QDRANT_PATH", "") or ""),
            dimension=dimension,
        )

    from app.services.vector_stores.chroma import ChromaVectorBackend

    return ChromaVectorBackend(
        collection_name=collection_name,
        persist_directory=str(
            _get(source, "CHROMA_PERSIST_DIRECTORY", "chroma_db")
        ),
    )


def get_vector_backend() -> Any:
    """默认 collection 的全局后端单例。"""
    global _backend_singleton
    if _backend_singleton is None:
        _backend_singleton = create_vector_backend()
    return _backend_singleton


def get_vector_store() -> Any:
    """兼容旧接口的全局 VectorStore 单例。"""
    global _vector_store_singleton
    if _vector_store_singleton is None:
        from app.services.vector_stores.legacy import VectorStore

        _vector_store_singleton = VectorStore()
    return _vector_store_singleton
