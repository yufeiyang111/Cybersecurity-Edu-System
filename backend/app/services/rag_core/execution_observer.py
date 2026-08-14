# -*- coding: utf-8 -*-
"""RAG 执行结果到低基数运行指标的非阻塞适配器。"""
from __future__ import annotations

from collections.abc import Mapping

from app.services.rag_core.contracts import RagExecutionResult
from app.services.rag_core.metrics import RagRuntimeMetrics


_ALLOWED_STAGES = (
    "candidate",
    "rerank",
    "evidence",
    "generation",
    "answer",
)


def record_execution_result(
    metrics: RagRuntimeMetrics | None,
    result: RagExecutionResult,
) -> RagExecutionResult:
    """尝试记录受控指标，观测失败绝不能影响用户回答。"""
    if metrics is None:
        return result
    try:
        metrics.record_execution(
            pipeline_mode="v2",
            pipeline_version=result.trace.pipeline_version_key,
            answer_status=result.answer_status,
            warnings=result.rag_warnings,
            stage_durations_ms=_stage_durations(result),
        )
    except Exception:
        return result
    return result


def _stage_durations(result: RagExecutionResult) -> dict[str, int]:
    summary = result.trace.stage_summary
    durations = {
        "retrieval_total": _duration(result.trace.retrieval_ms),
    }
    for stage in _ALLOWED_STAGES:
        value = summary.get(stage) if isinstance(summary, Mapping) else None
        if not isinstance(value, Mapping):
            continue
        duration = _duration(value.get("elapsed_ms"))
        if duration is not None:
            durations[stage] = duration
    return {
        key: value
        for key, value in durations.items()
        if value is not None
    }


def _duration(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer():
        normalized = int(value)
        return normalized if normalized >= 0 else None
    return None


__all__ = ["record_execution_result"]