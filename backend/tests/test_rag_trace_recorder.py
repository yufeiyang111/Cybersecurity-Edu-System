# -*- coding: utf-8 -*-
"""TraceRecorder 的数据最小化与持久化边界测试。"""
from app.services.rag_core.contracts import RetrievalTrace
from app.services.rag_core.metrics import RagRuntimeMetrics
from app.services.rag_core.trace_recorder import TraceRecorder


class _FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, value) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.added[-1].id = 73


def test_trace_recorder_persists_only_redacted_stage_summary():
    trace = RetrievalTrace(
        request_id="request-1",
        query_fingerprint="a" * 64,
        pipeline_version_key="rag-v2-test",
        stage_summary={
            "candidate_count": 3,
            "rerank": {"status": "applied", "elapsed_ms": 12},
            "query": "不得保存的问题原文",
            "evidence": {"content": "不得保存的资料正文"},
            "provider": {"reasoning": "不得保存的 CoT"},
        },
        warnings=("RERANKER_DEGRADED",),
        retrieval_ms=28,
    )
    session = _FakeSession()

    trace_id = TraceRecorder(session=session).record(
        user_id=7,
        trace=trace,
        record_id=11,
    )

    stored = session.added[0]
    assert trace_id == 73
    assert stored.user_id == 7
    assert stored.record_id == 11
    assert stored.query_fingerprint == "a" * 64
    assert stored.stage_summary_json == {
        "candidate_count": 3,
        "rerank": {"status": "applied", "elapsed_ms": 12},
        "evidence": {},
        "provider": {},
    }
    assert "TRACE_SENSITIVE_FIELD_REDACTED" in stored.warnings_json
    assert "不得保存" not in str(stored.stage_summary_json)
    assert "不得保存" not in str(stored.warnings_json)

class _FailingSession(_FakeSession):
    def __init__(self) -> None:
        super().__init__()
        self.rolled_back = False

    def flush(self) -> None:
        raise RuntimeError("database details must not be logged")

    def rollback(self) -> None:
        self.rolled_back = True


def test_trace_recorder_failure_is_non_blocking_and_logs_safe_context(caplog):
    trace = RetrievalTrace(
        request_id="request-safe-1",
        query_fingerprint="b" * 64,
        pipeline_version_key="rag-v2-test",
        stage_summary={"query": "不得泄漏的问题原文"},
    )
    session = _FailingSession()
    metrics = RagRuntimeMetrics(sample_limit=16)

    trace_id = TraceRecorder(session=session, metrics=metrics).try_record(
        user_id=7,
        trace=trace,
        stage="trace_persistence",
    )

    assert trace_id is None
    assert session.rolled_back is True
    assert "trace_persistence" in caplog.text
    assert "request-safe-1" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "不得泄漏" not in caplog.text
    assert "database details" not in caplog.text
    snapshot = metrics.snapshot()
    assert snapshot["series"][0]["component_events"]["trace_db"]["failed"] == 1
