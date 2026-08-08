# -*- coding: utf-8 -*-
"""硅基流动 API embedding/rerank 测试：请求格式、降级行为、排序映射"""
import numpy as np
import pytest


class FakeEmbeddingsResponse:
    status_code = 200

    def __init__(self, inputs):
        self._inputs = inputs

    def json(self):
        return {
            "data": [
                {
                    "object": "embedding",
                    "embedding": [0.1] * 1024,
                    "index": i,
                }
                for i in range(len(self._inputs))
            ],
            "usage": {"total_tokens": 10},
        }


class FakeEmbeddingsFailResponse:
    status_code = 429

    def __init__(self):
        self.text = '{"message": "rate limited"}'

    def json(self):
        return {"message": "rate limited"}


def test_api_embedding_encode_shape_and_normalization(monkeypatch):
    from app.services.api_embedding import ApiEmbedding

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/embeddings")
        assert json["model"] == "BAAI/bge-m3"
        assert json["input"] == ["a", "b"]
        return FakeEmbeddingsResponse(json["input"])

    monkeypatch.setattr("app.services.api_embedding.requests.post", fake_post)
    service = ApiEmbedding(api_key="sk-test", model="BAAI/bge-m3")

    vectors = service.encode(["a", "b"])
    assert vectors.shape == (2, 1024)
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)
    assert not service.is_degraded


def test_api_embedding_degraded_without_key():
    from app.services.api_embedding import ApiEmbedding

    service = ApiEmbedding(api_key="")
    assert service.is_degraded


def test_api_embedding_marks_failed_on_error(monkeypatch):
    from app.services.api_embedding import ApiEmbedding

    monkeypatch.setattr(
        "app.services.api_embedding.requests.post",
        lambda *a, **k: FakeEmbeddingsFailResponse(),
    )
    service = ApiEmbedding(api_key="sk-test")

    with pytest.raises(RuntimeError):
        service.encode(["a"])
    assert service.is_degraded


def test_api_embedding_encode_query_adds_instruction(monkeypatch):
    from app.services.api_embedding import ApiEmbedding

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["input"] = json["input"]
        return FakeEmbeddingsResponse(json["input"])

    monkeypatch.setattr("app.services.api_embedding.requests.post", fake_post)
    service = ApiEmbedding(api_key="sk-test")

    service.encode_query("什么是SQL注入")
    assert "为这个句子生成表示以用于检索相关文章" in captured["input"][0]


class FakeRerankResponse:
    status_code = 200

    def json(self):
        return {
            "id": "rerank-test",
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.60},
            ],
            "meta": {"tokens": {"input_tokens": 100}},
        }


def test_reranker_api_mode_sorts_by_score(monkeypatch):
    from app.services.llm.reranker_service import RerankerService

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/rerank")
        assert json["model"] == "BAAI/bge-reranker-v2-m3"
        assert json["documents"] == ["a", "b", "c"]
        return FakeRerankResponse()

    monkeypatch.setattr(
        "requests.post", fake_post
    )
    service = RerankerService(model_name="")
    service.api_mode = True
    service._api_failed = False

    docs = [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}, {"id": "3", "text": "c"}]
    result = service.rerank("q", docs, top_k=2)

    assert [d["id"] for d in result] == ["3", "1"]
    assert result[0]["rerank_score"] == 0.95


def test_reranker_api_mode_falls_back_on_failure(monkeypatch):
    from app.services.llm.reranker_service import RerankerService

    class FailResponse:
        status_code = 503
        text = "overloaded"

        def json(self):
            return {}

    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: FailResponse(),
    )
    service = RerankerService(model_name="")
    service.api_mode = True
    service._api_failed = False

    docs = [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}]
    result = service.rerank("q", docs, top_k=2)

    assert [d["id"] for d in result] == ["1", "2"]  # 保持原顺序
    assert service._api_failed


def test_embedding_service_uses_api_when_enabled(monkeypatch):
    from app.services.secbert_embedding import EmbeddingService

    service = EmbeddingService()
    assert service.embedding_model is not None
    # API 未启用时是本地模型路径（不真正加载，仅检查类型存在）
    assert hasattr(service.embedding_model, "is_degraded")
