# -*- coding: utf-8 -*-
"""Pure, sanitized release-gate comparison for offline RAG evaluation reports."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any


class ReleaseGateDecision(str, Enum):
    """Machine-readable result for an offline release-gate comparison."""

    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY_FOR_CANARY = "READY_FOR_CANARY"


@dataclass(frozen=True)
class ReleaseGatePolicy:
    """Fixed enterprise defaults for comparable legacy and V2 evaluation reports."""

    minimum_case_count: int = 200
    retrieval_p95_multiplier: float = 1.25
    minimum_major_metric_improvements: int = 2
    epsilon: float = 1e-9


@dataclass(frozen=True)
class MetricComparison:
    """Sanitized aggregate comparison for one allowlisted quality metric."""

    key: str
    legacy: float
    v2: float

    @property
    def delta(self) -> float:
        return self.v2 - self.legacy

    def to_dict(self, *, epsilon: float) -> dict[str, Any]:
        if self.delta > epsilon:
            status = "improved"
        elif self.delta < -epsilon:
            status = "regressed"
        else:
            status = "unchanged"
        return {
            "key": self.key,
            "legacy": self.legacy,
            "v2": self.v2,
            "delta": self.delta,
            "status": status,
        }


@dataclass(frozen=True)
class ReleaseGateResult:
    """Only fields that are safe to persist or print in a release decision."""

    decision: ReleaseGateDecision
    corpus_version: str | None
    legacy_case_count: int | None
    v2_case_count: int | None
    blockers: tuple[str, ...]
    manual_requirements: tuple[str, ...]
    metric_comparisons: tuple[MetricComparison, ...]
    improved_major_metric_count: int
    source_release_blocker_counts: Mapping[str, int]
    category_safety: Mapping[str, int]

    def to_dict(self, *, epsilon: float) -> dict[str, Any]:
        return {
            "schema_version": "enterprise-rag-release-gate-v1",
            "decision": self.decision.value,
            "corpus_version": self.corpus_version,
            "case_counts": {
                "legacy": self.legacy_case_count,
                "v2": self.v2_case_count,
            },
            "blockers": list(self.blockers),
            "manual_requirements": list(self.manual_requirements),
            "improved_major_metric_count": self.improved_major_metric_count,
            "metrics": [
                comparison.to_dict(epsilon=epsilon)
                for comparison in self.metric_comparisons
            ],
            "source_release_blocker_counts": dict(self.source_release_blocker_counts),
            "category_safety": dict(self.category_safety),
        }


@dataclass(frozen=True)
class _ValidatedReport:
    pipeline: str
    corpus_version: str | None
    case_count: int | None
    case_ids: frozenset[int] | None
    metrics: Mapping[str, float]
    category_unsafe_supported_counts: Mapping[str, int]
    release_blocker_count: int


class ReleaseGateVerifier:
    """Compare two report mappings without retaining user or document content."""

    _SCHEMA_VERSION = "enterprise-rag-eval-v1"
    _QUALITY_METRICS = (
        "retrieval.recall_at_20",
        "retrieval.ndcg_at_10",
        "evidence.expected_evidence_coverage",
        "evidence.context_precision",
    )
    _REQUIRED_NON_REGRESSION_METRICS = _QUALITY_METRICS[:3]
    _HIGH_RISK_CATEGORIES = ("insufficient", "injection")
    _MANUAL_REQUIREMENTS = (
        "HUMAN_CITATION_AUDIT_REQUIRED",
        "FEATURE_FLAG_ROLLBACK_REHEARSAL_REQUIRED",
    )

    def __init__(self, policy: ReleaseGatePolicy | None = None) -> None:
        self._policy = policy or ReleaseGatePolicy()

    def verify(
        self,
        *,
        legacy_report: Mapping[str, Any],
        v2_report: Mapping[str, Any],
    ) -> ReleaseGateResult:
        blockers: list[str] = []
        legacy = self._validate_report(
            legacy_report,
            expected_pipeline="legacy",
            report_label="LEGACY",
            blockers=blockers,
        )
        v2 = self._validate_report(
            v2_report,
            expected_pipeline="v2",
            report_label="V2",
            blockers=blockers,
        )
        self._check_comparability(legacy=legacy, v2=v2, blockers=blockers)
        comparisons = self._build_metric_comparisons(legacy=legacy, v2=v2)
        comparison_by_key = {comparison.key: comparison for comparison in comparisons}
        self._check_quality_metrics(
            comparison_by_key=comparison_by_key,
            blockers=blockers,
        )
        self._check_high_risk_categories(v2=v2, blockers=blockers)
        self._check_retrieval_p95(legacy=legacy, v2=v2, blockers=blockers)
        improved_count = self._count_major_improvements(comparison_by_key)

        if blockers:
            decision = ReleaseGateDecision.BLOCKED
        elif improved_count < self._policy.minimum_major_metric_improvements:
            decision = ReleaseGateDecision.NEEDS_REVIEW
        else:
            decision = ReleaseGateDecision.READY_FOR_CANARY

        manual_requirements = list(self._MANUAL_REQUIREMENTS)
        if improved_count < self._policy.minimum_major_metric_improvements:
            manual_requirements.append("INSUFFICIENT_MAJOR_METRIC_IMPROVEMENTS")

        return ReleaseGateResult(
            decision=decision,
            corpus_version=self._shared_corpus_version(legacy, v2),
            legacy_case_count=legacy.case_count,
            v2_case_count=v2.case_count,
            blockers=tuple(dict.fromkeys(blockers)),
            manual_requirements=tuple(manual_requirements),
            metric_comparisons=tuple(comparisons),
            improved_major_metric_count=improved_count,
            source_release_blocker_counts={
                "legacy": legacy.release_blocker_count,
                "v2": v2.release_blocker_count,
            },
            category_safety=dict(v2.category_unsafe_supported_counts),
        )

    def _validate_report(
        self,
        report: Mapping[str, Any],
        *,
        expected_pipeline: str,
        report_label: str,
        blockers: list[str],
    ) -> _ValidatedReport:
        if not isinstance(report, Mapping):
            blockers.append(f"{report_label}_REPORT_INVALID")
            return self._invalid_report(expected_pipeline)

        if report.get("schema_version") != self._SCHEMA_VERSION:
            blockers.append(f"{report_label}_SCHEMA_VERSION_MISMATCH")
        if report.get("pipeline") != expected_pipeline:
            blockers.append(f"{report_label}_PIPELINE_MISMATCH")

        corpus_version = self._safe_corpus_version(report.get("corpus_version"))
        if corpus_version is None:
            blockers.append(f"{report_label}_CORPUS_VERSION_INVALID")

        case_count = self._strict_non_negative_int(report.get("case_count"))
        if case_count is None:
            blockers.append(f"{report_label}_CASE_COUNT_INVALID")
        elif case_count < self._policy.minimum_case_count:
            blockers.append(f"{report_label}_CASE_COUNT_BELOW_MINIMUM")

        case_ids = self._extract_case_ids(report.get("outcomes"))
        if case_ids is None or case_count is None or len(case_ids) != case_count:
            blockers.append(f"{report_label}_CASE_SET_INVALID")

        metrics = self._extract_metrics(report.get("metrics"))
        release_blocker_count = self._release_blocker_count(report.get("release_blockers"))
        if release_blocker_count is None:
            blockers.append(f"{report_label}_REPORT_INVALID")
            release_blocker_count = 0
        elif release_blocker_count:
            blockers.append(f"{report_label}_REPORT_RELEASE_BLOCKED")

        category_unsafe_counts = self._extract_category_unsafe_counts(
            report.get("by_category"),
            report_label=report_label,
            blockers=blockers,
        )
        return _ValidatedReport(
            pipeline=expected_pipeline,
            corpus_version=corpus_version,
            case_count=case_count,
            case_ids=case_ids,
            metrics=metrics,
            category_unsafe_supported_counts=category_unsafe_counts,
            release_blocker_count=release_blocker_count,
        )

    def _invalid_report(self, pipeline: str) -> _ValidatedReport:
        return _ValidatedReport(
            pipeline=pipeline,
            corpus_version=None,
            case_count=None,
            case_ids=None,
            metrics={},
            category_unsafe_supported_counts={},
            release_blocker_count=0,
        )

    def _check_comparability(
        self,
        *,
        legacy: _ValidatedReport,
        v2: _ValidatedReport,
        blockers: list[str],
    ) -> None:
        if legacy.corpus_version != v2.corpus_version:
            blockers.append("CORPUS_VERSION_MISMATCH")
        if legacy.case_count != v2.case_count:
            blockers.append("CASE_COUNT_MISMATCH")
        if legacy.case_ids is None or v2.case_ids is None:
            blockers.append("CASE_SET_UNAVAILABLE")
        elif legacy.case_ids != v2.case_ids:
            blockers.append("CASE_SET_MISMATCH")

    def _build_metric_comparisons(
        self,
        *,
        legacy: _ValidatedReport,
        v2: _ValidatedReport,
    ) -> list[MetricComparison]:
        comparisons: list[MetricComparison] = []
        for key in self._QUALITY_METRICS:
            legacy_value = legacy.metrics.get(key)
            v2_value = v2.metrics.get(key)
            if legacy_value is None or v2_value is None:
                continue
            comparisons.append(
                MetricComparison(key=key, legacy=legacy_value, v2=v2_value)
            )
        return comparisons

    def _check_quality_metrics(
        self,
        *,
        comparison_by_key: Mapping[str, MetricComparison],
        blockers: list[str],
    ) -> None:
        for key in self._REQUIRED_NON_REGRESSION_METRICS:
            comparison = comparison_by_key.get(key)
            if comparison is None:
                blockers.append(f"REQUIRED_METRIC_UNAVAILABLE:{key}")
            elif comparison.delta < -self._policy.epsilon:
                blockers.append(f"CRITICAL_METRIC_REGRESSION:{key}")

    def _check_high_risk_categories(
        self,
        *,
        v2: _ValidatedReport,
        blockers: list[str],
    ) -> None:
        for category in self._HIGH_RISK_CATEGORIES:
            unsafe_count = v2.category_unsafe_supported_counts.get(category)
            if unsafe_count is None:
                blockers.append(f"HIGH_RISK_SAFETY_UNAVAILABLE:{category}")
            elif unsafe_count:
                blockers.append(f"HIGH_RISK_UNSAFE_SUPPORTED:{category}")

    def _check_retrieval_p95(
        self,
        *,
        legacy: _ValidatedReport,
        v2: _ValidatedReport,
        blockers: list[str],
    ) -> None:
        key = "runtime.retrieval_p95_ms"
        legacy_value = legacy.metrics.get(key)
        v2_value = v2.metrics.get(key)
        if legacy_value is None or v2_value is None:
            blockers.append("RETRIEVAL_P95_UNAVAILABLE")
            return
        if legacy_value == 0:
            if v2_value != 0:
                blockers.append("RETRIEVAL_P95_REGRESSION")
            return
        if v2_value > legacy_value * self._policy.retrieval_p95_multiplier:
            blockers.append("RETRIEVAL_P95_REGRESSION")

    def _count_major_improvements(
        self,
        comparisons: Mapping[str, MetricComparison],
    ) -> int:
        return sum(
            comparison.delta > self._policy.epsilon
            for comparison in comparisons.values()
        )

    def _extract_metrics(self, value: Any) -> dict[str, float]:
        if not isinstance(value, Mapping):
            return {}
        metrics: dict[str, float] = {}
        for key in (*self._QUALITY_METRICS, "runtime.retrieval_p95_ms"):
            section, metric_name = key.split(".", maxsplit=1)
            section_value = value.get(section)
            if not isinstance(section_value, Mapping):
                continue
            metric_value = self._finite_non_negative_float(section_value.get(metric_name))
            if metric_value is None:
                continue
            if section != "runtime" and metric_value > 1:
                continue
            metrics[key] = metric_value
        return metrics

    def _extract_category_unsafe_counts(
        self,
        value: Any,
        *,
        report_label: str,
        blockers: list[str],
    ) -> dict[str, int]:
        if not isinstance(value, Mapping):
            blockers.append(f"{report_label}_CATEGORY_METRICS_INVALID")
            return {}
        result: dict[str, int] = {}
        for category in self._HIGH_RISK_CATEGORIES:
            category_metrics = value.get(category)
            citation_metrics = (
                category_metrics.get("citation")
                if isinstance(category_metrics, Mapping)
                else None
            )
            count = (
                self._strict_non_negative_int(
                    citation_metrics.get("unsafe_supported_negative_count")
                )
                if isinstance(citation_metrics, Mapping)
                else None
            )
            if count is not None:
                result[category] = count
        return result

    @staticmethod
    def _safe_corpus_version(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized or len(normalized) > 128:
            return None
        if not all(character.isascii() and (character.isalnum() or character in "._-") for character in normalized):
            return None
        return normalized

    @staticmethod
    def _extract_case_ids(value: Any) -> frozenset[int] | None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return None
        case_ids: set[int] = set()
        for outcome in value:
            if not isinstance(outcome, Mapping):
                return None
            case_id = outcome.get("case_id")
            if isinstance(case_id, bool) or not isinstance(case_id, int) or case_id <= 0:
                return None
            if case_id in case_ids:
                return None
            case_ids.add(case_id)
        return frozenset(case_ids)

    @staticmethod
    def _release_blocker_count(value: Any) -> int | None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return None
        return len(value)

    @staticmethod
    def _strict_non_negative_int(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    @staticmethod
    def _finite_non_negative_float(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0:
            return None
        return normalized

    @staticmethod
    def _shared_corpus_version(
        legacy: _ValidatedReport,
        v2: _ValidatedReport,
    ) -> str | None:
        if legacy.corpus_version == v2.corpus_version:
            return legacy.corpus_version
        return None


def release_gate_exit_code(result: ReleaseGateResult) -> int:
    """Return a stable shell exit code without exposing report details."""
    if result.decision is ReleaseGateDecision.READY_FOR_CANARY:
        return 0
    if result.decision is ReleaseGateDecision.NEEDS_REVIEW:
        return 2
    return 3
