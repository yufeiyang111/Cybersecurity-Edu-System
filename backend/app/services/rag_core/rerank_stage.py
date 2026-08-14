# -*- coding: utf-8 -*-
"""RAG 候选重排适配层：复用既有 reranker，并对不可信返回安全降级。"""
from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import math
from time import perf_counter
from typing import Any, Literal, Mapping, Protocol, Sequence

from app.services.rag_core.contracts import Candidate

logger = logging.getLogger(__name__)

RerankStatus = Literal["applied", "skipped", "failed"]


class RerankerPort(Protocol):
    """现有 reranker 服务在 RAG Core 中使用的最小公开接口。"""

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """返回带可信 ``rerank_score`` 的重排文档。"""


@dataclass(frozen=True)
class RerankResult:
    """重排阶段的无正文执行结果，可安全放入 trace。"""

    candidates: tuple[Candidate, ...]
    status: RerankStatus
    input_count: int
    output_count: int
    elapsed_ms: int
    failure_type: str | None = None

    def trace_summary(self) -> dict[str, Any]:
        """返回脱敏的阶段摘要，禁止携带 query 和证据正文。"""
        return {
            "status": self.status,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "elapsed_ms": self.elapsed_ms,
            "failure_type": self.failure_type,
        }


class RerankStage:
    """将候选块安全接入既有重排 Provider。"""

    def __init__(self, reranker: RerankerPort | None = None) -> None:
        self._reranker = reranker

    def rerank(
        self,
        query: str,
        candidates: Sequence[Candidate],
        *,
        top_k: int,
    ) -> RerankResult:
        """重排候选；无法验证的结果必须回退到原始 RRF 顺序。"""
        started_at = perf_counter()
        original = tuple(candidates)
        limit = min(max(top_k, 0), len(original))
        fallback = original[:limit]

        if not original:
            return self._result(
                candidates=(),
                status="skipped",
                input_count=0,
                started_at=started_at,
                failure_type="empty_candidates",
            )
        if limit == 0:
            return self._result(
                candidates=(),
                status="skipped",
                input_count=len(original),
                started_at=started_at,
                failure_type="non_positive_top_k",
            )

        reranker = self._reranker or _default_reranker()
        documents = [
            {
                "id": str(index),
                "text": candidate.content,
            }
            for index, candidate in enumerate(original)
        ]
        try:
            returned = reranker.rerank(query, documents, top_k=limit)
        except Exception as exc:
            logger.warning(
                "RAG rerank stage failed error_type=%s",
                type(exc).__name__,
            )
            return self._result(
                candidates=fallback,
                status="failed",
                input_count=len(original),
                started_at=started_at,
                failure_type=type(exc).__name__,
            )

        scored = _validated_scored_candidates(
            returned=returned,
            candidates=original,
            expected_count=limit,
        )
        if scored is None:
            return self._result(
                candidates=fallback,
                status="skipped",
                input_count=len(original),
                started_at=started_at,
                failure_type="unscored_response",
            )

        return self._result(
            candidates=scored,
            status="applied",
            input_count=len(original),
            started_at=started_at,
        )

    @staticmethod
    def _result(
        *,
        candidates: tuple[Candidate, ...],
        status: RerankStatus,
        input_count: int,
        started_at: float,
        failure_type: str | None = None,
    ) -> RerankResult:
        return RerankResult(
            candidates=candidates,
            status=status,
            input_count=input_count,
            output_count=len(candidates),
            elapsed_ms=max(0, round((perf_counter() - started_at) * 1000)),
            failure_type=failure_type,
        )


def _default_reranker() -> RerankerPort:
    """延迟获取现有服务，避免模块导入时触发 Provider 初始化。"""
    from app.services.llm.reranker_service import get_reranker_service

    return get_reranker_service()


def _validated_scored_candidates(
    *,
    returned: object,
    candidates: tuple[Candidate, ...],
    expected_count: int,
) -> tuple[Candidate, ...] | None:
    """验证 Provider 返回的完整性后再采纳 score，避免伪重排。"""
    if not isinstance(returned, list) or len(returned) != expected_count:
        return None

    scored: list[tuple[int, Candidate]] = []
    seen_indexes: set[int] = set()
    for response_rank, item in enumerate(returned):
        if not isinstance(item, Mapping):
            return None
        candidate_index = _candidate_index(item.get("id"), len(candidates))
        score = _score(item.get("rerank_score"))
        if candidate_index is None or score is None or candidate_index in seen_indexes:
            return None
        seen_indexes.add(candidate_index)
        scored.append(
            (
                response_rank,
                replace(candidates[candidate_index], rerank_score=score),
            )
        )

    scored.sort(
        key=lambda item: (
            -float(item[1].rerank_score),
            item[0],
        )
    )
    return tuple(candidate for _, candidate in scored)


def _candidate_index(value: object, candidate_count: int) -> int | None:
    """仅接受 stage 自己生成的候选序号，拒绝 Provider 伪造的标识。"""
    if isinstance(value, bool):
        return None
    try:
        index = int(str(value))
    except (TypeError, ValueError):
        return None
    return index if 0 <= index < candidate_count else None


def _score(value: object) -> float | None:
    """仅接受有限的数值分数，避免 NaN/Infinity 污染排序。"""
    if isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) else None


__all__ = [
    "RerankResult",
    "RerankStage",
    "RerankStatus",
]
