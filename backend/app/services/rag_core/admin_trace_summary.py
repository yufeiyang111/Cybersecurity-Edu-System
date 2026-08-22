# -*- coding: utf-8 -*-
"""管理员 RAG 诊断的阶段摘要白名单，禁止向浏览器下发候选明细。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_ALLOWED_RETRIEVAL_PATHS = (
    "dense_only",
    "bm25_only",
    "both",
    "lexical_only_degraded",
    "legacy",
    "unknown",
)
_ALLOWED_REJECTION_COUNTS = (
    "document_diversity",
    "token_counter_failure",
    "token_budget",
    "empty_content",
    "missing_location",
    "prompt_injection",
    "duplicate",
)
_ALLOWED_RERANK_STATUSES = {"completed", "failed", "skipped"}
_ALLOWED_ANSWER_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "ungrounded",
    "degraded",
}


def build_admin_trace_stage_summary(summary: object) -> dict[str, dict[str, Any]]:
    """仅保留诊断页需要的聚合计数、状态和耗时，拒绝候选明细。"""
    source = summary if isinstance(summary, Mapping) else {}
    candidate = _stage(source, "candidate")
    if not candidate:
        candidate = source
    return {
        "candidate": _candidate_summary(candidate),
        "rerank": _rerank_summary(_stage(source, "rerank")),
        "evidence": _evidence_summary(_stage(source, "evidence")),
        "answer": _answer_summary(_stage(source, "answer")),
    }


def _candidate_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    retrieval_paths = _count_map(
        source.get("retrieval_paths"),
        allowed_keys=_ALLOWED_RETRIEVAL_PATHS,
    )
    return _without_none({
        "candidate_count": _non_negative_int(source.get("candidate_count")),
        "degraded": source.get("degraded") if isinstance(source.get("degraded"), bool) else None,
        "retrieval_paths": retrieval_paths,
    })


def _rerank_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    status = source.get("status")
    return _without_none({
        "status": status if status in _ALLOWED_RERANK_STATUSES else None,
        "input_count": _non_negative_int(source.get("input_count")),
        "output_count": _non_negative_int(source.get("output_count")),
        "elapsed_ms": _non_negative_int(source.get("elapsed_ms")),
    })


def _evidence_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    status = source.get("answer_status")
    return _without_none({
        "answer_status": status if status in _ALLOWED_ANSWER_STATUSES else None,
        "reference_count": _non_negative_int(source.get("reference_count")),
        "token_count": _non_negative_int(source.get("token_count")),
        "token_budget": _positive_int(source.get("token_budget")),
        "rejection_counts": _count_map(
            source.get("rejection_counts"),
            allowed_keys=_ALLOWED_REJECTION_COUNTS,
        ),
    })


def _answer_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    status = source.get("answer_status")
    return _without_none({
        "answer_status": status if status in _ALLOWED_ANSWER_STATUSES else None,
        "citation_count": _non_negative_int(source.get("citation_count")),
        "claim_count": _non_negative_int(source.get("claim_count")),
        "warning_count": _non_negative_int(source.get("warning_count")),
    })


def _stage(source: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = source.get(key)
    return value if isinstance(value, Mapping) else {}


def _count_map(value: object, *, allowed_keys: tuple[str, ...]) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: count
        for key in allowed_keys
        if (count := _non_negative_int(value.get(key))) is not None
    }


def _without_none(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item is not None
    }


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def _positive_int(value: object) -> int | None:
    normalized = _non_negative_int(value)
    return normalized if normalized and normalized > 0 else None
