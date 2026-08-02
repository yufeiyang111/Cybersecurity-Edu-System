"""Chroma 向量后端实现（本地持久化模式）。"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import chromadb

from app.services.vector_stores.contracts import VectorHit


class ChromaVectorBackend:
    """基于 ChromaDB 的向量后端，collection 名与持久化目录可配置。"""

    def __init__(self, *, collection_name: str, persist_directory: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "CyberGuard vector index"},
        )

    def upsert(
        self,
        *,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        texts: Sequence[str],
        metadatas: Sequence[Mapping[str, Any]],
    ) -> int:
        self._collection.upsert(
            ids=list(ids),
            embeddings=[[float(value) for value in vector] for vector in vectors],
            documents=list(texts),
            metadatas=[dict(metadata) for metadata in metadatas],
        )
        return len(list(ids))

    def search(
        self,
        *,
        vector: Sequence[float],
        where: Optional[Mapping[str, Any]],
        top_k: int,
    ) -> list[VectorHit]:
        results = self._collection.query(
            query_embeddings=[[float(value) for value in vector]],
            n_results=top_k,
            where=dict(where) if where else None,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[VectorHit] = []
        if results.get("ids") and results["ids"]:
            for index, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][index]
                hits.append(
                    VectorHit(
                        id=str(doc_id),
                        text=results["documents"][0][index],
                        metadata=dict(results["metadatas"][0][index] or {}),
                        similarity=1.0 / (1.0 + float(distance)),
                        distance=float(distance),
                    )
                )
        return hits

    def delete(self, *, where: Mapping[str, Any]) -> None:
        if where:
            self._collection.delete(where=dict(where))

    def delete_by_ids(self, *, ids: Sequence[str]) -> None:
        if ids:
            self._collection.delete(ids=list(ids))

    def delete_all(self) -> bool:
        try:
            name = self._collection.name
            self._client.delete_collection(name)
            self._collection = self._client.get_or_create_collection(
                name=name,
                metadata={"description": "CyberGuard vector index"},
            )
            return True
        except Exception:
            return False

    def count(self) -> int:
        return self._collection.count()
