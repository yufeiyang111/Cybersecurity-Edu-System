"""向量后端协议与共享类型。

协议只负责向量与元数据的存取，不感知 embedding 模型；
文本编码由调用方（legacy VectorStore / SecurityKnowledgeIndex）完成。

当前实现：ChromaVectorBackend（本地持久化）、QdrantVectorBackend（server/本地模式）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

import numpy as np

DEFAULT_COLLECTION_NAME = "knowledge_embeddings"
SECURITY_KNOWLEDGE_COLLECTION_NAME = "security_knowledge_embeddings"


def to_2d_list(vector: np.ndarray) -> list[list[float]]:
    """把 (dim,)、(1, dim)、(batch, seq, dim) 等任意形状规整为 (1, dim) 的 list。"""
    if vector.ndim == 1:
        vector = vector.reshape(1, -1)
    elif vector.ndim == 2:
        if vector.shape[0] > 1:
            vector = vector[0:1, :]
    elif vector.ndim == 3:
        vector = vector[0, 0, :].reshape(1, -1)
    else:
        vector = vector.flatten().reshape(1, -1)
    return vector.tolist()


@dataclass(frozen=True)
class VectorHit:
    id: str
    text: str
    metadata: Mapping[str, Any]
    similarity: float | None
    distance: float
    retrieval_metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": dict(self.metadata),
            "similarity": self.similarity,
            "distance": self.distance,
            "retrieval_metadata": dict(self.retrieval_metadata),
        }


@runtime_checkable
class VectorBackend(Protocol):
    """向量后端契约：只做向量与元数据存取，不做 embedding。"""

    def upsert(
        self,
        *,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        texts: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]],
    ) -> int:
        """写入/覆盖文档，返回写入条数。"""
        ...

    def search(
        self,
        *,
        vector: Sequence[float],
        where: Optional[Mapping[str, Any]],
        top_k: int,
    ) -> list[VectorHit]:
        """按元数据过滤 + 向量相似度检索。"""
        ...

    def delete(self, *, where: Mapping[str, Any]) -> None:
        """按元数据条件删除。"""
        ...

    def delete_by_ids(self, *, ids: Sequence[str]) -> None:
        """按文档 id 删除。"""
        ...

    def delete_all(self) -> bool:
        """清空并重建 collection。"""
        ...

    def count(self) -> int:
        """返回当前文档数。"""
        ...
