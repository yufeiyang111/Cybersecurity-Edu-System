# -*- coding: utf-8 -*-
"""企业 RAG 离线评测的纯指标计算。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from math import log2
from typing import Any

from .contracts import CitationManifest, EvidenceReference

_NEGATIVE_STATUSES = {
    "insufficient_evidence",
    "conflicting_evidence",
    "degraded",
}


def retrieval_metrics(
    *,
    expected_document_ids: Iterable[object],
    candidate_document_ids: Iterable[object],
) -> dict[str, Any]:
    """计算 Candidate 层的 Recall、MRR、nDCG，不把无标签 case 当作零分。"""
    expected = _normalized_ids(expected_document_ids)
    candidates = _normalized_ids(candidate_document_ids)
    if not expected:
        return {
            "judged": False,
            "recall_at_20": None,
            "recall_at_40": None,
            "mrr_at_20": None,
            "ndcg_at_10": None,
            "first_relevant_rank": None,
        }

    expected_set = set(expected)
    first_relevant_rank = next(
        (
            rank
            for rank, document_id in enumerate(candidates, start=1)
            if document_id in expected_set
        ),
        None,
    )
    return {
        "judged": True,
        "recall_at_20": _recall_at(candidates, expected_set, 20),
        "recall_at_40": _recall_at(candidates, expected_set, 40),
        "mrr_at_20": (
            1.0 / first_relevant_rank
            if first_relevant_rank is not None and first_relevant_rank <= 20
            else 0.0
        ),
        "ndcg_at_10": _ndcg_at(candidates, expected_set, 10),
        "first_relevant_rank": first_relevant_rank,
    }


def evidence_pack_metrics(
    *,
    expected_document_ids: Iterable[object],
    references: Sequence[EvidenceReference],
    token_count: object,
    token_budget: object,
) -> dict[str, Any]:
    """计算最终 Evidence Pack 的覆盖、噪声、多样性与预算占用。"""
    expected = set(_normalized_ids(expected_document_ids))
    selected_document_ids = _normalized_ids(
        reference.document_id for reference in references
    )
    selected_set = set(selected_document_ids)
    matched = selected_set & expected
    reference_count = len(references)
    unique_source_count = len(
        {
            reference.source.strip()
            for reference in references
            if isinstance(reference.source, str) and reference.source.strip()
        }
    )
    evaluated = bool(expected)
    precision = (
        len(matched) / len(selected_set)
        if evaluated and selected_set
        else (0.0 if evaluated else None)
    )
    return {
        "judged": evaluated,
        "expected_evidence_coverage": len(matched) / len(expected) if expected else None,
        "context_precision": precision,
        "noise_ratio": 1.0 - precision if precision is not None else None,
        "source_diversity": unique_source_count / reference_count if reference_count else 0.0,
        "reference_count": reference_count,
        "unique_document_count": len(selected_set),
        "token_count": _non_negative_int(token_count),
        "token_budget": _positive_int(token_budget),
        "token_utilization": _token_utilization(token_count, token_budget),
    }


def citation_determinism_metrics(
    *,
    manifest: CitationManifest,
    actual_status: str | None,
    expected_status: str,
    status_observable: bool,
    citation_observable: bool,
) -> dict[str, Any]:
    """验证答案状态和 claim citation 是否能由本次 Evidence Pack 确定。"""
    available_ids = [reference.citation_id for reference in manifest.references]
    available_set = {citation_id for citation_id in available_ids if citation_id}
    duplicate_reference_ids = len(available_ids) - len(available_set)
    claim_ids: list[str] = []
    malformed_claim_count = 0
    for citation_ids in manifest.claim_citations.values():
        if not isinstance(citation_ids, Sequence) or isinstance(citation_ids, (str, bytes)):
            malformed_claim_count += 1
            continue
        for citation_id in citation_ids:
            if isinstance(citation_id, str) and citation_id.strip():
                claim_ids.append(citation_id.strip())
            else:
                malformed_claim_count += 1
    unknown_ids = sorted({citation_id for citation_id in claim_ids if citation_id not in available_set})
    duplicate_claim_ids = len(claim_ids) - len(set(claim_ids))
    status_matches_expected = actual_status == expected_status if status_observable else None
    unsafe_supported_negative = bool(
        status_observable
        and actual_status == "supported"
        and expected_status in _NEGATIVE_STATUSES
    )
    has_required_claim_citations = (
        bool(claim_ids)
        if actual_status == "supported" and citation_observable
        else True
    )
    citations_belong_to_pack = not unknown_ids and not malformed_claim_count
    is_deterministic = (
        citations_belong_to_pack
        and duplicate_reference_ids == 0
        and duplicate_claim_ids == 0
        and has_required_claim_citations
        and not unsafe_supported_negative
        if citation_observable
        else None
    )
    return {
        "citation_observable": citation_observable,
        "status_observable": status_observable,
        "status_matches_expected": status_matches_expected,
        "citation_count": len(available_set),
        "claim_count": len(manifest.claim_citations),
        "claim_citation_count": len(claim_ids),
        "unknown_citation_count": len(unknown_ids),
        "malformed_claim_count": malformed_claim_count,
        "duplicate_reference_id_count": duplicate_reference_ids,
        "duplicate_claim_citation_count": duplicate_claim_ids,
        "citations_belong_to_pack": citations_belong_to_pack,
        "unsafe_supported_negative": unsafe_supported_negative,
        "is_deterministic": is_deterministic,
    }


def percentile(values: Iterable[object], quantile: float) -> float | None:
    """使用线性插值计算分位数；空数据集不伪造零值。"""
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    normalized = sorted(
        number
        for value in values
        if (number := _finite_number(value)) is not None
    )
    if not normalized:
        return None
    if len(normalized) == 1:
        return normalized[0]
    position = (len(normalized) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(normalized) - 1)
    fraction = position - lower
    return normalized[lower] + (normalized[upper] - normalized[lower]) * fraction


def average_metric_values(
    rows: Iterable[Mapping[str, Any]],
    keys: Sequence[str],
) -> dict[str, float | None]:
    """按字段求均值，跳过 None 与非法数值，避免未标注 case 污染分数。"""
    result: dict[str, float | None] = {}
    for key in keys:
        values = [
            number
            for row in rows
            if (number := _finite_number(row.get(key))) is not None
        ]
        result[key] = sum(values) / len(values) if values else None
    return result


def _normalized_ids(values: Iterable[object]) -> tuple[str, ...]:
    unique: dict[str, None] = {}
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        normalized = str(value).strip()
        if normalized:
            unique.setdefault(normalized, None)
    return tuple(unique)


def _recall_at(candidates: Sequence[str], expected: set[str], cutoff: int) -> float:
    return len(set(candidates[:cutoff]) & expected) / len(expected)


def _ndcg_at(candidates: Sequence[str], expected: set[str], cutoff: int) -> float:
    dcg = sum(
        1.0 / log2(rank + 1)
        for rank, document_id in enumerate(candidates[:cutoff], start=1)
        if document_id in expected
    )
    ideal_count = min(len(expected), cutoff)
    ideal_dcg = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _positive_int(value: object) -> int | None:
    number = _non_negative_int(value)
    return number if number and number > 0 else None


def _token_utilization(token_count: object, token_budget: object) -> float | None:
    count = _non_negative_int(token_count)
    budget = _positive_int(token_budget)
    return count / budget if count is not None and budget is not None else None


__all__ = [
    "average_metric_values",
    "citation_determinism_metrics",
    "evidence_pack_metrics",
    "percentile",
    "retrieval_metrics",
]
