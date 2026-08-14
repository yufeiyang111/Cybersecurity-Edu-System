# -*- coding: utf-8 -*-
"""Rerank Stage 的降级和排序边界测试。"""
from app.services.rag_core.contracts import Candidate
from app.services.rag_core.rerank_stage import RerankStage


def _candidate(document_id: str, rrf_score: float) -> Candidate:
    return Candidate(
        document_id=document_id,
        title=f"文档 {document_id}",
        content=f"仅测试用证据 {document_id}",
        rrf_score=rrf_score,
        rank=int(document_id),
        retrieval_path="both",
    )


def test_unscored_rerank_response_keeps_original_rrf_order_and_trace_safe():
    class UnscoredReranker:
        def __init__(self) -> None:
            self.calls = []

        def rerank(self, query, documents, top_k):
            self.calls.append((query, documents, top_k))
            # 模拟 Provider 降级：没有可信分数，且故意返回错误顺序。
            return [documents[1], documents[0]]

    reranker = UnscoredReranker()
    candidates = (
        _candidate("1", 0.90),
        _candidate("2", 0.70),
        _candidate("3", 0.50),
    )

    result = RerankStage(reranker=reranker).rerank(
        "包含敏感查询文本的问题",
        candidates,
        top_k=2,
    )

    assert [candidate.document_id for candidate in result.candidates] == ["1", "2"]
    assert result.status == "skipped"
    assert result.input_count == 3
    assert result.output_count == 2
    assert result.failure_type == "unscored_response"
    assert reranker.calls[0][2] == 2
    assert "包含敏感查询文本的问题" not in str(result.trace_summary())
    assert "仅测试用证据" not in str(result.trace_summary())


def test_scored_response_reorders_only_with_finite_scores():
    class ScoredReranker:
        def rerank(self, query, documents, top_k):
            assert top_k == 2
            return [
                {"id": "0", "rerank_score": 0.20},
                {"id": "1", "rerank_score": 0.90},
            ]

    candidates = (
        _candidate("1", 0.90),
        _candidate("2", 0.70),
        _candidate("3", 0.50),
    )

    result = RerankStage(reranker=ScoredReranker()).rerank(
        "测试问题",
        candidates,
        top_k=2,
    )

    assert result.status == "applied"
    assert [candidate.document_id for candidate in result.candidates] == ["2", "1"]
    assert [candidate.rerank_score for candidate in result.candidates] == [0.90, 0.20]
    assert result.failure_type is None


def test_partial_or_non_finite_scores_are_rejected_without_changing_rrf_order():
    class InvalidReranker:
        def __init__(self, response) -> None:
            self._response = response

        def rerank(self, query, documents, top_k):
            return self._response

    candidates = (
        _candidate("1", 0.90),
        _candidate("2", 0.70),
    )
    invalid_responses = (
        [{"id": "0", "rerank_score": 0.9}],
        [
            {"id": "0", "rerank_score": 0.9},
            {"id": "1", "rerank_score": float("nan")},
        ],
        [
            {"id": "0", "rerank_score": 0.9},
            {"id": "0", "rerank_score": 0.8},
        ],
    )

    for response in invalid_responses:
        result = RerankStage(reranker=InvalidReranker(response)).rerank(
            "测试问题",
            candidates,
            top_k=2,
        )

        assert result.status == "skipped"
        assert [candidate.document_id for candidate in result.candidates] == ["1", "2"]
        assert all(candidate.rerank_score is None for candidate in result.candidates)


def test_rerank_exception_is_observable_but_preserves_safe_fallback():
    class BrokenReranker:
        def rerank(self, query, documents, top_k):
            raise RuntimeError("provider failure must not become a response body")

    candidates = (_candidate("1", 0.90),)

    result = RerankStage(reranker=BrokenReranker()).rerank(
        "测试问题",
        candidates,
        top_k=1,
    )

    assert result.status == "failed"
    assert result.failure_type == "RuntimeError"
    assert [candidate.document_id for candidate in result.candidates] == ["1"]
    assert "provider failure" not in str(result.trace_summary())


def test_empty_candidates_or_non_positive_top_k_do_not_call_reranker():
    class MustNotCallReranker:
        def __init__(self) -> None:
            self.calls = 0

        def rerank(self, query, documents, top_k):
            self.calls += 1
            raise AssertionError("this boundary must not call the provider")

    reranker = MustNotCallReranker()
    stage = RerankStage(reranker=reranker)

    empty = stage.rerank("测试问题", (), top_k=2)
    zero_limit = stage.rerank("测试问题", (_candidate("1", 0.90),), top_k=0)

    assert empty.status == "skipped"
    assert empty.failure_type == "empty_candidates"
    assert zero_limit.status == "skipped"
    assert zero_limit.failure_type == "non_positive_top_k"
    assert zero_limit.candidates == ()
    assert reranker.calls == 0
