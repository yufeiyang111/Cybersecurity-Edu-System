"""Qdrant 向量后端实现（server 模式优先，本地持久化模式兜底）。

注意：Qdrant 的 point id 只接受整数或合法 UUID，任意字符串 id 会被稳定映射为
UUID v5，原始 id 保存在 payload["id"]，对外完全透明。

混合检索（BM25 词法 + 稠密向量）：
- collection 配置 sparse vector（modifier=idf，Qdrant 原生 BM25，无需 inference 服务）；
- 写入时用 jieba 分词词频生成 sparse 向量（解决中文无空格分词问题）；
- 查询走 Query API 双路召回 + RRF 融合（Qdrant 服务端融合）。
"""
from __future__ import annotations

import logging
import os
import uuid
import zlib
from collections import Counter
from typing import Any, Mapping, Optional, Sequence

from app.services.vector_stores.contracts import VectorHit

logger = logging.getLogger(__name__)

# sparse vector 的命名向量名
BM25_VECTOR_NAME = "bm25"
DENSE_VECTOR_NAME = "dense"


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


def _zh_tokens(text: str) -> list[str]:
    """jieba 空格分词（中文 BM25 词法字段）。"""
    try:
        import jieba

        return [token for token in jieba.cut(str(text or "")) if token.strip()]
    except Exception:
        return list(str(text or ""))


def _sparse_vector_from_text(text: str) -> Any:
    """由文本生成 Qdrant sparse vector（词频，IDF 由 Qdrant modifier 处理）。"""
    from qdrant_client.models import SparseVector

    freq = Counter(_zh_tokens(text))
    if not freq:
        return SparseVector(indices=[0], values=[0.0])
    return SparseVector(
        indices=[zlib.crc32(token.encode("utf-8")) for token in freq],
        values=[float(count) for count in freq.values()],
    )


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
        from qdrant_client.models import (
            Modifier,
            SparseVectorParams,
            VectorParams,
        )

        existing = {item.name for item in self._client.get_collections().collections}
        if self._collection_name not in existing:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: VectorParams(
                        size=self._resolve_dimension(),
                        distance=self._distance,
                    )
                },
                sparse_vectors_config={
                    BM25_VECTOR_NAME: SparseVectorParams(
                        modifier=Modifier.IDF,
                    )
                },
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
                vector={
                    DENSE_VECTOR_NAME: [float(value) for value in vector],
                    BM25_VECTOR_NAME: _sparse_vector_from_text(text),
                },
                payload=_clean_payload(
                    {
                        **dict(metadata),
                        "id": str(point_id),
                        "text": text,
                    }
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
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=[float(value) for value in vector],
            using=DENSE_VECTOR_NAME,
            query_filter=self._filter(where) if where else None,
            limit=top_k,
            with_payload=True,
        )
        return self._to_hits(response)

    def hybrid_search(
        self,
        *,
        vector: Optional[Sequence[float]],
        text: str,
        where: Optional[Mapping[str, Any]],
        top_k: int,
    ) -> list[VectorHit]:
        """执行一次 dense、一次 BM25 查询，用本地 RRF 融合并保留阶段元数据。"""
        query_filter = self._filter(where) if where else None
        sparse_query = _sparse_vector_from_text(text)
        if vector is None:
            lexical = self._client.query_points(
                collection_name=self._collection_name,
                query=sparse_query,
                using=BM25_VECTOR_NAME,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
            return [
                self._hybrid_hit(
                    point,
                    similarity=None,
                    retrieval_metadata={
                        "dense_score": None,
                        "dense_rank": None,
                        "bm25_score": float(point.score),
                        "bm25_rank": rank,
                        "rrf_score": None,
                        "retrieval_path": "lexical_only_degraded",
                    },
                )
                for rank, point in enumerate(getattr(lexical, "points", None) or [], 1)
            ]

        dense = self._client.query_points(
            collection_name=self._collection_name,
            query=[float(value) for value in vector],
            using=DENSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=top_k * 2,
            with_payload=True,
        )
        lexical = self._client.query_points(
            collection_name=self._collection_name,
            query=sparse_query,
            using=BM25_VECTOR_NAME,
            query_filter=query_filter,
            limit=top_k * 2,
            with_payload=True,
        )
        fused: dict[str, dict[str, Any]] = {}
        for rank, point in enumerate(getattr(dense, "points", None) or [], 1):
            point_id = self._point_id(point)
            item = fused.setdefault(point_id, {"point": point, "rrf_score": 0.0})
            item.update({"point": point, "dense_score": float(point.score), "dense_rank": rank})
            item["rrf_score"] += 1.0 / (60 + rank)
        for rank, point in enumerate(getattr(lexical, "points", None) or [], 1):
            point_id = self._point_id(point)
            item = fused.setdefault(point_id, {"point": point, "rrf_score": 0.0})
            item.setdefault("point", point)
            item.update({"bm25_score": float(point.score), "bm25_rank": rank})
            item["rrf_score"] += 1.0 / (60 + rank)
        result=[]
        for item in sorted(fused.values(), key=lambda value: value["rrf_score"], reverse=True)[:top_k]:
            dense_rank=item.get("dense_rank")
            bm25_rank=item.get("bm25_rank")
            path="both" if dense_rank and bm25_rank else "dense_only" if dense_rank else "bm25_only"
            result.append(self._hybrid_hit(
                item["point"],
                similarity=item.get("dense_score"),
                retrieval_metadata={
                    "dense_score": item.get("dense_score"),
                    "dense_rank": dense_rank,
                    "bm25_score": item.get("bm25_score"),
                    "bm25_rank": bm25_rank,
                    "rrf_score": float(item["rrf_score"]),
                    "retrieval_path": path,
                },
            ))
        return result

    @staticmethod
    def _point_id(point: Any) -> str:
        payload = dict(point.payload or {})
        return str(payload.get("id", point.id))

    def _hybrid_hit(self, point: Any, *, similarity: float | None, retrieval_metadata: Mapping[str, Any]) -> VectorHit:
        payload = dict(point.payload or {})
        return VectorHit(
            id=str(payload.get("id", point.id)),
            text=str(payload.get("text", "")),
            metadata={key: value for key, value in payload.items() if key not in ("id", "text")},
            similarity=similarity,
            distance=1.0 if similarity is None else 1.0 - similarity,
            retrieval_metadata=dict(retrieval_metadata),
        )
    def _to_hits(self, response: Any) -> list[VectorHit]:
        hits: list[VectorHit] = []
        for point in getattr(response, "points", None) or []:
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
