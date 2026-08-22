# -*- coding: utf-8 -*-
"""企业 RAG 离线评测不可变数据契约。"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

EvaluationPipeline = Literal["legacy", "v2"]


@dataclass(frozen=True)
class EvaluationCase:
    """评测标签；query 只在内存执行期使用，不会进入报告。"""

    case_id: int
    case_key: str
    category: str
    difficulty: str
    expected_document_ids: tuple[str, ...]
    expected_status: str
    review_note: str
    query: str = field(default="", repr=False, compare=False)
    # 版本化评测集的富证据标签（可选，向后兼容 legacy 调用方）。
    # expected_evidence 每项携带 document_id / title / chunk_id / start_line /
    # end_line / corpus_version / role；绝不携带知识库正文或 Prompt。
    expected_evidence: tuple[dict, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.case_id <= 0:
            raise ValueError("case_id must be positive")
        if not self.case_key.strip():
            raise ValueError("case_key is required")
        if not self.category.strip() or not self.difficulty.strip():
            raise ValueError("category and difficulty are required")
        if not self.expected_status.strip():
            raise ValueError("expected_status is required")
        if not isinstance(self.expected_evidence, tuple):
            raise ValueError("expected_evidence must be a tuple")
        if not isinstance(self.tags, tuple):
            raise ValueError("tags must be a tuple")


@dataclass(frozen=True)
class EvaluationExecution:
    """单 case 的无正文执行摘要，由策略适配器提供。"""

    candidate_document_ids: tuple[str, ...]
    evidence_references: tuple[Any, ...]
    citation_manifest: Any
    answer_status: str | None
    status_observable: bool
    citation_observable: bool
    pipeline_version_key: str
    corpus_version: str
    config_fingerprint: str
    retrieval_ms: int | None = None
    rerank_ms: int | None = None
    evidence_token_count: int | None = None
    evidence_token_budget: int | None = None

    def __post_init__(self) -> None:
        if not self.pipeline_version_key.strip():
            raise ValueError("pipeline_version_key is required")
        if not self.corpus_version.strip():
            raise ValueError("corpus_version is required")
        if not self.config_fingerprint.strip():
            raise ValueError("config_fingerprint is required")


@dataclass(frozen=True)
class EvaluationCaseOutcome:
    """可安全存储、导出的单 case 结果。"""

    case_id: int
    category: str
    difficulty: str
    expected_status: str
    retrieval_metrics: Mapping[str, Any]
    evidence_metrics: Mapping[str, Any]
    citation_metrics: Mapping[str, Any]
    failure_stage: str | None
    notes: tuple[str, ...]
    retrieval_ms: int | None
    rerank_ms: int | None

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "retrieval_metrics": dict(self.retrieval_metrics),
            "citation_metrics": dict(self.citation_metrics),
            "answer_metrics": {
                "expected_status": self.expected_status,
                "failure_stage": self.failure_stage,
                "notes": list(self.notes),
            },
            "failure_stage": self.failure_stage,
            "notes": ",".join(self.notes)[:1000] or None,
        }

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "expected_status": self.expected_status,
            "retrieval_metrics": dict(self.retrieval_metrics),
            "evidence_metrics": dict(self.evidence_metrics),
            "citation_metrics": dict(self.citation_metrics),
            "failure_stage": self.failure_stage,
            "notes": list(self.notes),
            "retrieval_ms": self.retrieval_ms,
            "rerank_ms": self.rerank_ms,
        }


@dataclass(frozen=True)
class EvaluationReport:
    """不含 query、正文、Prompt 和模型回答的评测报告。"""

    pipeline: EvaluationPipeline
    corpus_version: str
    pipeline_version_keys: tuple[str, ...]
    config_fingerprints: tuple[str, ...]
    outcomes: tuple[EvaluationCaseOutcome, ...]
    metrics: Mapping[str, Any]
    by_category: Mapping[str, Mapping[str, Any]]
    by_difficulty: Mapping[str, Mapping[str, Any]]
    release_blockers: tuple[str, ...]
    started_at: datetime
    finished_at: datetime

    @property
    def case_count(self) -> int:
        return len(self.outcomes)

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "enterprise-rag-eval-v1",
            "pipeline": self.pipeline,
            "corpus_version": self.corpus_version,
            "pipeline_version_keys": list(self.pipeline_version_keys),
            "config_fingerprints": list(self.config_fingerprints),
            "case_count": self.case_count,
            "metrics": dict(self.metrics),
            "by_category": {
                category: dict(metrics)
                for category, metrics in self.by_category.items()
            },
            "by_difficulty": {
                difficulty: dict(metrics)
                for difficulty, metrics in self.by_difficulty.items()
            },
            "release_blockers": list(self.release_blockers),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "outcomes": [outcome.to_report_dict() for outcome in self.outcomes],
        }


__all__ = [
    "EvaluationCase",
    "EvaluationCaseOutcome",
    "EvaluationExecution",
    "EvaluationPipeline",
    "EvaluationReport",
]