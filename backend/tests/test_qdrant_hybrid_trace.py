# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.services.vector_stores.qdrant import BM25_VECTOR_NAME, DENSE_VECTOR_NAME, QdrantVectorBackend


def _point(point_id, score):
    return SimpleNamespace(id=point_id, score=score, payload={"id": point_id, "text": point_id, "doc_id": point_id})


def test_hybrid_search_queries_dense_and_bm25_once_and_exposes_trace():
    backend = object.__new__(QdrantVectorBackend)
    backend._collection_name = "test"
    backend._filter = lambda where: None
    calls = []
    def query_points(**kwargs):
        calls.append(kwargs["using"])
        points = [_point("both", 0.9), _point("dense", 0.8)] if kwargs["using"] == DENSE_VECTOR_NAME else [_point("both", 3.0), _point("bm25", 2.0)]
        return SimpleNamespace(points=points)
    backend._client = SimpleNamespace(query_points=query_points)
    hits = backend.hybrid_search(vector=[0.1, 0.2], text="CVE-2024-1", where=None, top_k=3)
    assert calls == [DENSE_VECTOR_NAME, BM25_VECTOR_NAME]
    metadata = {hit.id: hit.retrieval_metadata for hit in hits}
    assert metadata["both"]["retrieval_path"] == "both"
    assert metadata["dense"]["retrieval_path"] == "dense_only"
    assert metadata["bm25"]["retrieval_path"] == "bm25_only"


def test_hybrid_search_degraded_path_has_no_fake_similarity():
    backend = object.__new__(QdrantVectorBackend)
    backend._collection_name = "test"
    backend._filter = lambda where: None
    backend._client = SimpleNamespace(query_points=lambda **kwargs: SimpleNamespace(points=[_point("lexical", 4.0)]))
    hit = backend.hybrid_search(vector=None, text="443 端口", where=None, top_k=1)[0]
    assert hit.similarity is None
    assert hit.retrieval_metadata["retrieval_path"] == "lexical_only_degraded"