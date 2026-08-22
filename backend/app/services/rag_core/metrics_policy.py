# -*- coding: utf-8 -*-
"""Validation and serialization policy for bounded RAG runtime metrics."""
from __future__ import annotations

import re
from collections.abc import Sequence
from math import ceil
from typing import Any


ALLOWED_MODES = {"legacy", "v2", "unknown"}
ALLOWED_ANSWER_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "ungrounded",
    "degraded",
    "unclassified",
}
ALLOWED_STAGES = (
    "candidate",
    "rerank",
    "evidence",
    "generation",
    "ungrounded_generation",
    "answer",
    "retrieval_total",
)
ALLOWED_COMPONENTS = (
    "embedding",
    "qdrant",
    "reranker",
    "llm",
    "citation_validator",
    "trace_db",
    "other",
)
ALLOWED_OUTCOMES = {"degraded", "failed"}
WARNING_EVENTS = {
    "EMBEDDING_DEGRADED": ("embedding", "degraded"),
    "EMBEDDING_UNAVAILABLE": ("embedding", "failed"),
    "QDRANT_UNAVAILABLE": ("qdrant", "failed"),
    "RERANKER_DEGRADED": ("reranker", "degraded"),
    "RERANKER_UNAVAILABLE": ("reranker", "failed"),
    "RERANK_FAILED": ("reranker", "failed"),
    "RERANK_SKIPPED": ("reranker", "degraded"),
    "LLM_PROVIDER_REQUEST_FAILED": ("llm", "failed"),
    "CITATION_VALIDATION_FAILED": ("citation_validator", "failed"),
    "CITATION_VALIDATOR_UNAVAILABLE": ("citation_validator", "failed"),
    "STRICT_CITATION_REJECTED": ("citation_validator", "degraded"),
}

_V2_PIPELINE_VERSION_PATTERN = re.compile(r"rag-v2-[0-9a-f]{24}")
_LEGACY_PIPELINE_VERSION = "legacy-enhanced-rag-v1"


def normalize_mode(value: object) -> str:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    return normalized if normalized in ALLOWED_MODES else "unknown"


def normalize_pipeline_version(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().lower()
    if _V2_PIPELINE_VERSION_PATTERN.fullmatch(normalized):
        return normalized
    if normalized == _LEGACY_PIPELINE_VERSION:
        return normalized
    return "unknown"


def normalize_answer_status(value: object) -> str:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    return normalized if normalized in ALLOWED_ANSWER_STATUSES else "unclassified"


def normalize_component(value: object) -> str:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    return normalized if normalized in ALLOWED_COMPONENTS else "other"


def normalize_outcome(value: object) -> str | None:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    return normalized if normalized in ALLOWED_OUTCOMES else None


def normalize_duration(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 3_600_000 else None
    if isinstance(value, float) and value.is_integer():
        normalized = int(value)
        return normalized if 0 <= normalized <= 3_600_000 else None
    return None


def duration_summary(samples: Sequence[int]) -> dict[str, int]:
    ordered = sorted(samples)
    if not ordered:
        return {"count": 0, "p50": 0, "p95": 0}
    return {
        "count": len(ordered),
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
    }


def _percentile(values: Sequence[int], percentile: float) -> int:
    position = max(0, min(len(values) - 1, ceil(len(values) * percentile) - 1))
    return values[position]


__all__ = [
    "ALLOWED_ANSWER_STATUSES",
    "ALLOWED_COMPONENTS",
    "ALLOWED_OUTCOMES",
    "ALLOWED_STAGES",
    "WARNING_EVENTS",
    "duration_summary",
    "normalize_answer_status",
    "normalize_component",
    "normalize_duration",
    "normalize_mode",
    "normalize_outcome",
    "normalize_pipeline_version",
]
