# -*- coding: utf-8 -*-
"""企业 RAG 离线评测编排与脱敏报告聚合。"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
import logging
from typing import Any

from .contracts import CitationManifest
from .evaluation_contracts import (
    EvaluationCase,
    EvaluationCaseOutcome,
    EvaluationExecution,
    EvaluationPipeline,
    EvaluationReport,
)
from .evaluation_metrics import (
    average_metric_values,
    citation_determinism_metrics,
    evidence_pack_metrics,
    percentile,
    retrieval_metrics,
)

logger = logging.getLogger(__name__)
ExecutionPort = Callable[[EvaluationCase], EvaluationExecution]


class OfflineRagEvaluator:
    """深模块：统一执行、评分、归因与报告脱敏。"""

    def __init__(self, *, execute_case: ExecutionPort) -> None:
        self._execute_case = execute_case

    def evaluate(
        self,
        cases: Iterable[EvaluationCase],
        *,
        pipeline: EvaluationPipeline,
        corpus_version: str,
    ) -> EvaluationReport:
        if pipeline not in {"legacy", "v2"}:
            raise ValueError("pipeline must be 'legacy' or 'v2'")
        normalized_corpus = corpus_version.strip()
        if not normalized_corpus:
            raise ValueError("corpus_version is required")

        started_at = datetime.utcnow()
        outcomes: list[EvaluationCaseOutcome] = []
        versions: set[str] = set()
        fingerprints: set[str] = set()
        for case in cases:
            outcome, execution = self._evaluate_case(case, normalized_corpus)
            outcomes.append(outcome)
            if execution is not None:
                versions.add(execution.pipeline_version_key)
                fingerprints.add(execution.config_fingerprint)
        ordered_outcomes = tuple(outcomes)
        return EvaluationReport(
            pipeline=pipeline,
            corpus_version=normalized_corpus,
            pipeline_version_keys=tuple(sorted(versions)),
            config_fingerprints=tuple(sorted(fingerprints)),
            outcomes=ordered_outcomes,
            metrics=_summary_metrics(ordered_outcomes),
            by_category=_category_metrics(ordered_outcomes),
            release_blockers=_release_blockers(ordered_outcomes),
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )

    def _evaluate_case(
        self,
        case: EvaluationCase,
        expected_corpus_version: str,
    ) -> tuple[EvaluationCaseOutcome, EvaluationExecution | None]:
        try:
            execution = self._execute_case(case)
        except Exception as exc:
            logger.warning(
                "RAG evaluation execution failed case_id=%s error_type=%s",
                case.case_id,
                type(exc).__name__,
            )
            return _failed_outcome(case, "execution", "EVALUATION_EXECUTION_FAILED"), None
        if execution.corpus_version != expected_corpus_version:
            logger.warning("RAG evaluation corpus mismatch case_id=%s", case.case_id)
            return _failed_outcome(case, "version", "CORPUS_VERSION_MISMATCH"), execution

        retrieval = retrieval_metrics(
            expected_document_ids=case.expected_document_ids,
            candidate_document_ids=execution.candidate_document_ids,
        )
        evidence = evidence_pack_metrics(
            expected_document_ids=case.expected_document_ids,
            references=execution.evidence_references,
            token_count=execution.evidence_token_count,
            token_budget=execution.evidence_token_budget,
        )
        citations = citation_determinism_metrics(
            manifest=execution.citation_manifest,
            actual_status=execution.answer_status,
            expected_status=case.expected_status,
            status_observable=execution.status_observable,
            citation_observable=execution.citation_observable,
        )
        return (
            EvaluationCaseOutcome(
                case_id=case.case_id,
                category=case.category,
                difficulty=case.difficulty,
                expected_status=case.expected_status,
                retrieval_metrics=retrieval,
                evidence_metrics=evidence,
                citation_metrics=citations,
                failure_stage=_failure_stage(retrieval, citations),
                notes=(),
                retrieval_ms=_non_negative_int(execution.retrieval_ms),
                rerank_ms=_non_negative_int(execution.rerank_ms),
            ),
            execution,
        )


def _failed_outcome(
    case: EvaluationCase,
    failure_stage: str,
    note: str,
) -> EvaluationCaseOutcome:
    return EvaluationCaseOutcome(
        case_id=case.case_id,
        category=case.category,
        difficulty=case.difficulty,
        expected_status=case.expected_status,
        retrieval_metrics=retrieval_metrics(
            expected_document_ids=case.expected_document_ids,
            candidate_document_ids=(),
        ),
        evidence_metrics=evidence_pack_metrics(
            expected_document_ids=case.expected_document_ids,
            references=(),
            token_count=None,
            token_budget=None,
        ),
        citation_metrics=citation_determinism_metrics(
            manifest=CitationManifest(references=()),
            actual_status=None,
            expected_status=case.expected_status,
            status_observable=False,
            citation_observable=False,
        ),
        failure_stage=failure_stage,
        notes=(note,),
        retrieval_ms=None,
        rerank_ms=None,
    )


def _summary_metrics(outcomes: Sequence[EvaluationCaseOutcome]) -> dict[str, Any]:
    retrieval_rows = [outcome.retrieval_metrics for outcome in outcomes]
    evidence_rows = [outcome.evidence_metrics for outcome in outcomes]
    citation_rows = [outcome.citation_metrics for outcome in outcomes]
    return {
        "retrieval": average_metric_values(
            retrieval_rows,
            ("recall_at_20", "recall_at_40", "mrr_at_20", "ndcg_at_10"),
        ),
        "evidence": average_metric_values(
            evidence_rows,
            ("expected_evidence_coverage", "context_precision", "noise_ratio", "source_diversity", "token_utilization"),
        ),
        "citation": {
            **average_metric_values(citation_rows, ("status_matches_expected", "citations_belong_to_pack", "is_deterministic")),
            "unsafe_supported_negative_count": sum(row.get("unsafe_supported_negative") is True for row in citation_rows),
        },
        "runtime": {
            "retrieval_p50_ms": percentile((outcome.retrieval_ms for outcome in outcomes), 0.5),
            "retrieval_p95_ms": percentile((outcome.retrieval_ms for outcome in outcomes), 0.95),
            "rerank_p50_ms": percentile((outcome.rerank_ms for outcome in outcomes), 0.5),
            "rerank_p95_ms": percentile((outcome.rerank_ms for outcome in outcomes), 0.95),
        },
        "failure_stages": dict(sorted(Counter(outcome.failure_stage for outcome in outcomes if outcome.failure_stage).items())),
    }


def _category_metrics(outcomes: Sequence[EvaluationCaseOutcome]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[EvaluationCaseOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[outcome.category].append(outcome)
    return {
        category: {"case_count": len(group), **_summary_metrics(tuple(group))}
        for category, group in sorted(grouped.items())
    }


def _release_blockers(outcomes: Sequence[EvaluationCaseOutcome]) -> tuple[str, ...]:
    blockers: list[str] = []
    if any(outcome.citation_metrics.get("unsafe_supported_negative") is True for outcome in outcomes):
        blockers.append("NEGATIVE_CASE_MARKED_SUPPORTED")
    if any(outcome.failure_stage == "execution" for outcome in outcomes):
        blockers.append("EVALUATION_EXECUTION_FAILED")
    if any(outcome.failure_stage == "version" for outcome in outcomes):
        blockers.append("CORPUS_VERSION_MISMATCH")
    return tuple(blockers)


def _failure_stage(retrieval: Mapping[str, Any], citations: Mapping[str, Any]) -> str | None:
    if citations.get("status_matches_expected") is False:
        return "answer_status"
    if citations.get("is_deterministic") is False:
        return "citation"
    recall = retrieval.get("recall_at_40")
    return "candidate" if recall is not None and recall < 1 else None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


__all__ = [
    "EvaluationCase",
    "EvaluationCaseOutcome",
    "EvaluationExecution",
    "EvaluationReport",
    "OfflineRagEvaluator",
]