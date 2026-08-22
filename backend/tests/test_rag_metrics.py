# -*- coding: utf-8 -*-
"""RAG runtime metrics boundary and data-minimization tests."""
from __future__ import annotations

import json

import pytest

from app.services.rag_core.metrics import RagRuntimeMetrics


def _series_for(snapshot: dict, *, mode: str, version: str) -> dict:
    return next(
        series
        for series in snapshot["series"]
        if series["pipeline_mode"] == mode
        and series["pipeline_version"] == version
    )


def test_runtime_metrics_aggregate_allowed_events_and_bounded_latency_percentiles():
    metrics = RagRuntimeMetrics(sample_limit=16)
    for duration in (10, 20, 30):
        metrics.record_execution(
            pipeline_mode="v2",
            pipeline_version="rag-v2-0123456789abcdef01234567",
            answer_status="degraded" if duration == 30 else "supported",
            warnings=(
                "EMBEDDING_DEGRADED",
                "CITATION_VALIDATION_FAILED" if duration == 30 else "UNKNOWN_WARNING",
            ),
            stage_durations_ms={
                "candidate": duration,
                "rerank": duration + 1,
                "retrieval_total": duration + 2,
                "query": 999,
            },
        )

    snapshot = metrics.snapshot()
    series = _series_for(
        snapshot,
        mode="v2",
        version="rag-v2-0123456789abcdef01234567",
    )

    assert snapshot["scope"] == "process"
    assert snapshot["sample_limit"] == 16
    assert series["execution_count"] == 3
    assert series["degraded_count"] == 1
    assert series["citation_validation_failure_count"] == 1
    assert series["answer_status_counts"]["supported"] == 2
    assert series["answer_status_counts"]["degraded"] == 1
    assert series["component_events"]["embedding"]["degraded"] == 3
    assert series["component_events"]["citation_validator"]["failed"] == 1
    assert series["durations_ms"]["candidate"] == {
        "count": 3,
        "p50": 20,
        "p95": 30,
    }
    assert "query" not in series["durations_ms"]


@pytest.mark.parametrize("sample_limit", [False, 15, 5001, "16"])
def test_runtime_metrics_rejects_invalid_sample_limits(sample_limit):
    with pytest.raises(ValueError, match="sample_limit"):
        RagRuntimeMetrics(sample_limit=sample_limit)


def test_runtime_metrics_coerce_untrusted_labels_and_do_not_store_raw_input():
    metrics = RagRuntimeMetrics(sample_limit=16)
    raw_query = "user query and document title must never become metric labels"
    metrics.record_execution(
        pipeline_mode=raw_query,
        pipeline_version="document title contains spaces",
        answer_status="invented-status",
        warnings=(raw_query, "RERANK_FAILED"),
        stage_durations_ms={
            "candidate": True,
            "generation": "123",
            "answer": -1,
        },
    )
    metrics.record_component_event(
        component=raw_query,
        outcome="success",
        pipeline_mode=raw_query,
        pipeline_version=raw_query,
    )

    snapshot = metrics.snapshot()
    series = _series_for(snapshot, mode="unknown", version="unknown")
    serialized = json.dumps(snapshot, ensure_ascii=False)

    assert series["answer_status_counts"]["unclassified"] == 1
    assert series["component_events"]["reranker"]["failed"] == 1
    assert series["durations_ms"] == {}
    assert raw_query not in serialized
    assert "document title contains spaces" not in serialized


def test_runtime_metrics_caps_pipeline_series_and_accounts_for_overflow():
    metrics = RagRuntimeMetrics(sample_limit=16)
    total_executions = 40
    for index in range(total_executions):
        metrics.record_execution(
            pipeline_mode="v2",
            pipeline_version=f"rag-v2-{index:024x}",
            answer_status="supported",
        )

    snapshot = metrics.snapshot()
    execution_count = sum(
        series["execution_count"]
        for series in snapshot["series"]
    )

    assert len(snapshot["series"]) <= 24
    assert execution_count == total_executions
    overflow = _series_for(snapshot, mode="unknown", version="other")
    assert overflow["execution_count"] == total_executions - 23


def test_runtime_metrics_tracks_ungrounded_answers_separately():
    metrics = RagRuntimeMetrics(sample_limit=16)
    metrics.record_execution(
        pipeline_mode="v2",
        pipeline_version="rag-v2-0123456789abcdef01234567",
        answer_status="ungrounded",
        stage_durations_ms={"ungrounded_generation": 27},
    )

    series = _series_for(
        metrics.snapshot(),
        mode="v2",
        version="rag-v2-0123456789abcdef01234567",
    )

    assert series["answer_status_counts"]["ungrounded"] == 1
    assert series["durations_ms"]["ungrounded_generation"] == {
        "count": 1,
        "p50": 27,
        "p95": 27,
    }
