# -*- coding: utf-8 -*-
"""Tests for the pure offline RAG release-gate verifier."""
from __future__ import annotations

import copy
import json

import pytest

from app.services.rag_core.release_gate import (
    ReleaseGateDecision,
    ReleaseGateVerifier,
    release_gate_exit_code,
)


CORPUS_VERSION = "public-knowledge-20260814"


def _report(
    pipeline: str,
    *,
    recall: float = 0.70,
    ndcg: float = 0.60,
    coverage: float = 0.65,
    precision: float = 0.55,
    retrieval_p95: float = 100.0,
) -> dict:
    return {
        "schema_version": "enterprise-rag-eval-v1",
        "pipeline": pipeline,
        "corpus_version": CORPUS_VERSION,
        "case_count": 200,
        "metrics": {
            "retrieval": {
                "recall_at_20": recall,
                "ndcg_at_10": ndcg,
            },
            "evidence": {
                "expected_evidence_coverage": coverage,
                "context_precision": precision,
            },
            "runtime": {"retrieval_p95_ms": retrieval_p95},
        },
        "by_category": {
            "insufficient": {
                "citation": {"unsafe_supported_negative_count": 0},
            },
            "injection": {
                "citation": {"unsafe_supported_negative_count": 0},
            },
        },
        "release_blockers": [],
        "outcomes": [
            {
                "case_id": case_id,
                "query": "private query must never be emitted",
                "title": "private title must never be emitted",
            }
            for case_id in range(1, 201)
        ],
        "unknown_untrusted_field": "private prompt must never be emitted",
    }


def _ready_pair() -> tuple[dict, dict]:
    legacy = _report("legacy")
    v2 = _report(
        "v2",
        recall=0.75,
        ndcg=0.66,
        coverage=0.69,
        precision=0.57,
        retrieval_p95=125.0,
    )
    return legacy, v2


def test_ready_decision_is_sanitized_and_does_not_mutate_inputs():
    legacy, v2 = _ready_pair()
    original_legacy = copy.deepcopy(legacy)
    original_v2 = copy.deepcopy(v2)

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)
    payload = result.to_dict(epsilon=1e-9)
    serialized = json.dumps(payload)

    assert result.decision is ReleaseGateDecision.READY_FOR_CANARY
    assert result.improved_major_metric_count == 4
    assert release_gate_exit_code(result) == 0
    assert payload["category_safety"] == {"insufficient": 0, "injection": 0}
    assert "HUMAN_CITATION_AUDIT_REQUIRED" in payload["manual_requirements"]
    assert "private query" not in serialized
    assert "private title" not in serialized
    assert "private prompt" not in serialized
    assert legacy == original_legacy
    assert v2 == original_v2


def test_retrieval_p95_at_exact_limit_is_allowed():
    legacy, v2 = _ready_pair()
    v2["metrics"]["runtime"]["retrieval_p95_ms"] = 125.0

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)

    assert result.decision is ReleaseGateDecision.READY_FOR_CANARY
    assert "RETRIEVAL_P95_REGRESSION" not in result.blockers


def test_retrieval_p95_above_limit_blocks_release():
    legacy, v2 = _ready_pair()
    v2["metrics"]["runtime"]["retrieval_p95_ms"] = 125.0001

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)

    assert result.decision is ReleaseGateDecision.BLOCKED
    assert "RETRIEVAL_P95_REGRESSION" in result.blockers
    assert release_gate_exit_code(result) == 3


def test_required_quality_regression_blocks_release():
    legacy, v2 = _ready_pair()
    v2["metrics"]["retrieval"]["ndcg_at_10"] = 0.59

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)

    assert result.decision is ReleaseGateDecision.BLOCKED
    assert "CRITICAL_METRIC_REGRESSION:retrieval.ndcg_at_10" in result.blockers


def test_single_major_metric_gain_needs_review_not_canary_ready():
    legacy = _report("legacy")
    v2 = _report("v2", recall=0.75)

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)

    assert result.decision is ReleaseGateDecision.NEEDS_REVIEW
    assert result.blockers == ()
    assert result.improved_major_metric_count == 1
    assert "INSUFFICIENT_MAJOR_METRIC_IMPROVEMENTS" in result.manual_requirements
    assert release_gate_exit_code(result) == 2


def test_unsafe_negative_and_untrusted_blocker_text_are_not_emitted():
    legacy, v2 = _ready_pair()
    v2["release_blockers"] = ["private malicious blocker text"]
    v2["by_category"]["injection"]["citation"][
        "unsafe_supported_negative_count"
    ] = 1

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)
    payload = result.to_dict(epsilon=1e-9)

    assert result.decision is ReleaseGateDecision.BLOCKED
    assert "V2_REPORT_RELEASE_BLOCKED" in result.blockers
    assert "HIGH_RISK_UNSAFE_SUPPORTED:injection" in result.blockers
    assert "private malicious blocker text" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("change", "expected_blocker"),
    [
        (lambda legacy, v2: legacy.update({"corpus_version": "other-corpus"}), "CORPUS_VERSION_MISMATCH"),
        (lambda legacy, v2: v2["outcomes"].pop(), "V2_CASE_SET_INVALID"),
        (lambda legacy, v2: v2["outcomes"].__setitem__(0, {"case_id": 999}), "CASE_SET_MISMATCH"),
    ],
)
def test_uncomparable_reports_are_blocked_without_case_ids(change, expected_blocker):
    legacy, v2 = _ready_pair()
    change(legacy, v2)

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)
    payload = result.to_dict(epsilon=1e-9)

    assert result.decision is ReleaseGateDecision.BLOCKED
    assert expected_blocker in result.blockers
    assert "case_id" not in json.dumps(payload)


def test_invalid_metric_and_non_mapping_report_are_blocked_safely():
    legacy, v2 = _ready_pair()
    legacy["metrics"]["retrieval"]["recall_at_20"] = float("nan")

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)
    malformed = ReleaseGateVerifier().verify(legacy_report=[], v2_report=v2)  # type: ignore[arg-type]

    assert "REQUIRED_METRIC_UNAVAILABLE:retrieval.recall_at_20" in result.blockers
    assert malformed.decision is ReleaseGateDecision.BLOCKED
    assert "LEGACY_REPORT_INVALID" in malformed.blockers
