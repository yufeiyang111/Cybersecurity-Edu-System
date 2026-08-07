# -*- coding: utf-8 -*-
"""reranker 服务测试：加载失败降级、batch 打分、排序行为"""
import pytest


def test_reranker_fallback_preserves_order(monkeypatch):
    from app.services.llm.reranker_service import RerankerService

    service = RerankerService(model_name="")

    monkeypatch.setattr(service, "_load", lambda: False)
    docs = [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}]
    assert service.rerank("q", docs, top_k=2) == docs
    assert service.rerank("q", [], top_k=2) == []


def test_reranker_empty_docs(monkeypatch):
    from app.services.llm.reranker_service import RerankerService

    service = RerankerService(model_name="")
    monkeypatch.setattr(service, "_load", lambda: True)
    assert service.rerank("q", [], top_k=5) == []


def test_reranker_batch_score_returns_none_on_failure(monkeypatch):
    from app.services.llm.reranker_service import RerankerService

    service = RerankerService(model_name="")
    monkeypatch.setattr(service, "_load", lambda: True)

    # 真实实现中 _batch_score 内部捕获异常并返回 None（打分失败整体降级）
    monkeypatch.setattr(service, "_batch_score", lambda query, passages: None)
    docs = [{"id": "1", "text": "a"}]
    assert service.rerank("q", docs, top_k=1) == docs


def test_reranker_sorts_by_score(monkeypatch):
    from app.services.llm.reranker_service import RerankerService

    service = RerankerService(model_name="")
    monkeypatch.setattr(service, "_load", lambda: True)
    monkeypatch.setattr(
        service,
        "_batch_score",
        lambda query, passages: [0.2, 0.9, 0.5],
    )
    docs = [
        {"id": "1", "text": "a"},
        {"id": "2", "text": "b"},
        {"id": "3", "text": "c"},
    ]
    result = service.rerank("q", docs, top_k=2)
    assert [d["id"] for d in result] == ["2", "3"]
    assert result[0]["rerank_score"] == 0.9


def test_engine_reranker_falls_back_when_model_missing(monkeypatch):
    from app.services.enhanced_rag_engine import Reranker

    monkeypatch.setattr(
        "app.services.llm.reranker_service.RerankerService._load",
        lambda self: False,
    )
    reranker = Reranker()
    docs = [
        {"id": "1", "text": "SQL注入防护", "score": 0.7},
        {"id": "2", "text": "XSS攻击原理", "score": 0.6},
    ]
    result = reranker.rerank("SQL注入", docs, top_k=2)
    # 降级路径仍返回全部（按相似度排序），不崩溃
    assert len(result) == 2
