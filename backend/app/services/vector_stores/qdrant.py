"""Qdrant 向量后端实现（server 模式优先，本地持久化模式兜底）。

注意：Qdrant 的 point id 只接受整数或合法 UUID，任意字符串 id 会被稳定映射为
UUID v5，原始 id 保存在 payload["id"]，对外完全透明。
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Mapping, Optional, Sequence

from app.services.vector_stores.contracts import VectorHit

logger = logging.getLogger(__name__)


def _ensure_local_no_proxy() -> None:
    """本机回环地址不经过系统代理。

    httpx（qdrant-client 的 HTTP 层）会读取 Windows 系统代理，若代理软件
    （如 Clash）拒绝转发回环目标，本地请求会得到 502。这里只在未显式配置
    NO_PROXY 时补充默认值。
    """
    if not os.environ.get("NO_PROXY"):
        os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
    if not os.environ.get("no_proxy"):
        os.environ["no_proxy"] = "127.0.0.1,localhost,::1"


def _stable_point_id(original: str) -> str:
    """把任意字符串文档 id 稳定映射为 UUID v5。"""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, str(original)))


def _clean_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Qdrant payload 不接受 None 值，过滤后返回。"""
    return {key: value for key, value in payload.items() if value is not None}


class QdrantVectorBackend:
    """基于 Qdrant 的向量后端。"""

    def __init__(
        self,
        *,
        collection_name: str,
        url: str = "",
        path: str = "",
        dimension: Optional[int] = None,
    ) -> None:
        _ensure_local_no_proxy()
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance

        self._collection_name = collection_name
        self._dimension = dimension
        self._distance = Distance.COSINE
        if url:
            self._client = QdrantClient(url=url, timeout=10)
        else:
            self._client = QdrantClient(path=path, timeout=10)
        self._ensure_collection()

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def _resolve_dimension(self) -> int:
        if self._dimension is None:
            from app.services.secbert_embedding import get_embedding_service

            self._dimension = int(get_embedding_service().dimension)
        return self._dimension

    def _ensure_collection(self) -> None:
        from qdrant_client.models import VectorParams

        existing = {item.name for item in self._client.get_collections().collections}
        if self._collection_name not in existing:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._resolve_dimension(),
                    distance=self._distance,
                ),
            )

    def _filter(self, where: Mapping[str, Any]) -> Any | None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        conditions = [
            FieldCondition(key=str(key), match=MatchValue(value=value))
            for key, value in where.items()
            if value is not None
        ]
        if not conditions:
            return None
        return Filter(must=conditions)

    def upsert(
        self,
        *,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        texts: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]],
    ) -> int:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=_stable_point_id(point_id),
                vector=[float(value) for value in vector],
                payload=_clean_payload(
                    {**dict(metadata), "id": str(point_id), "text": text}
                ),
            )
            for point_id, vector, text, metadata in zip(ids, vectors, texts, metadatas)
        ]
        if not points:
            return 0
        self._client.upsert(collection_name=self._collection_name, points=points)
        return len(points)

    def search(
        self,
        *,
        vector: Sequence[float],
        where: Optional[Mapping[str, Any]],
        top_k: int,
    ) -> list[VectorHit]:
        response = self._client.search(
            collection_name=self._collection_name,
            query_vector=[float(value) for value in vector],
            query_filter=self._filter(where) if where else None,
            limit=top_k,
            with_payload=True,
        )
        hits: list[VectorHit] = []
        for point in response:
            payload = dict(point.payload or {})
            similarity = float(point.score)
            hits.append(
                VectorHit(
                    id=str(payload.get("id", point.id)),
                    text=str(payload.get("text", "")),
                    metadata={
                        key: value
                        for key, value in payload.items()
                        if key not in ("id", "text")
                    },
                    similarity=similarity,
                    distance=1.0 - similarity,
                )
            )
        return hits

    def delete(self, *, where: Mapping[str, Any]) -> None:
        from qdrant_client.models import FilterSelector

        query_filter = self._filter(where)
        if query_filter is None:
            return
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=FilterSelector(filter=query_filter),
        )

    def delete_by_ids(self, *, ids: Sequence[str]) -> None:
        from qdrant_client.models import PointIdsList

        if not ids:
            return
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(
                points=[_stable_point_id(point_id) for point_id in ids]
            ),
        )

    def delete_all(self) -> bool:
        try:
            self._client.delete_collection(collection_name=self._collection_name)
            self._ensure_collection()
            return True
        except Exception:
            return False

    def count(self) -> int:
        return int(self._client.count(collection_name=self._collection_name, exact=True).count)
