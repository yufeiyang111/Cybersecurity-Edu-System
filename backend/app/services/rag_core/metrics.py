# -*- coding: utf-8 -*-
"""RAG 运行时低基数指标：仅保存受控计数和有界延迟样本。"""
from __future__ import annotations

from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from app.services.rag_core.metrics_policy import (
    ALLOWED_ANSWER_STATUSES,
    ALLOWED_COMPONENTS,
    ALLOWED_OUTCOMES,
    ALLOWED_STAGES,
    WARNING_EVENTS,
    duration_summary,
    normalize_answer_status,
    normalize_component,
    normalize_duration,
    normalize_mode,
    normalize_outcome,
    normalize_pipeline_version,
)


_MAX_SERIES = 24


@dataclass
class _MetricSeries:
    """单个受控 mode/version 序列的进程内聚合状态。"""

    mode: str
    pipeline_version: str
    execution_count: int = 0
    degraded_count: int = 0
    citation_validation_failure_count: int = 0
    answer_status_counts: Counter[str] = field(default_factory=Counter)
    component_events: dict[str, Counter[str]] = field(
        default_factory=lambda: {
            component: Counter()
            for component in ALLOWED_COMPONENTS
        }
    )
    durations_ms: dict[str, deque[int]] = field(default_factory=dict)


class RagRuntimeMetrics:
    """线程安全的进程内 RAG 指标注册表，不接受用户文本或文档标识。"""

    def __init__(self, *, sample_limit: int = 512) -> None:
        if isinstance(sample_limit, bool) or not isinstance(sample_limit, int):
            raise ValueError("sample_limit must be an integer")
        if not 16 <= sample_limit <= 5000:
            raise ValueError("sample_limit must be between 16 and 5000")
        self._sample_limit = sample_limit
        self._lock = Lock()
        self._series: dict[tuple[str, str], _MetricSeries] = {}

    def record_execution(
        self,
        *,
        pipeline_mode: object,
        pipeline_version: object,
        answer_status: object,
        warnings: Sequence[object] = (),
        stage_durations_ms: Mapping[str, object] | None = None,
    ) -> None:
        """记录一次完成的 RAG 执行；无效输入会收敛为固定受控桶。"""
        with self._lock:
            series = self._get_series(pipeline_mode, pipeline_version)
            status = normalize_answer_status(answer_status)
            series.execution_count += 1
            series.answer_status_counts[status] += 1
            if status == "degraded":
                series.degraded_count += 1
            self._record_warning_events(series, warnings)
            self._record_durations(series, stage_durations_ms)

    def record_component_event(
        self,
        *,
        component: object,
        outcome: object,
        pipeline_mode: object = "unknown",
        pipeline_version: object = "unknown",
    ) -> None:
        """记录不一定关联最终回答的组件降级或失败，例如 trace DB 写入。"""
        normalized_component = normalize_component(component)
        normalized_outcome = normalize_outcome(outcome)
        if normalized_outcome is None:
            return
        with self._lock:
            series = self._get_series(pipeline_mode, pipeline_version)
            series.component_events[normalized_component][normalized_outcome] += 1

    def snapshot(self) -> dict[str, Any]:
        """返回管理员可读的受控快照；明确其仅代表当前进程。"""
        with self._lock:
            entries = [
                _serialize_series(series)
                for _, series in sorted(self._series.items())
            ]
        return {
            "scope": "process",
            "sample_limit": self._sample_limit,
            "series": entries,
        }

    def clear(self) -> None:
        """仅供自动化测试重置进程内状态。"""
        with self._lock:
            self._series.clear()

    def _get_series(self, pipeline_mode: object, pipeline_version: object) -> _MetricSeries:
        mode = normalize_mode(pipeline_mode)
        version = normalize_pipeline_version(pipeline_version)
        key = (mode, version)
        existing = self._series.get(key)
        if existing is not None:
            return existing

        if len(self._series) >= _MAX_SERIES - 1:
            overflow_key = ("unknown", "other")
            overflow = self._series.get(overflow_key)
            if overflow is None:
                overflow = _MetricSeries(
                    mode=overflow_key[0],
                    pipeline_version=overflow_key[1],
                )
                self._series[overflow_key] = overflow
            return overflow

        series = _MetricSeries(mode=key[0], pipeline_version=key[1])
        self._series[key] = series
        return series

    def _record_warning_events(self, series: _MetricSeries, warnings: Sequence[object]) -> None:
        for warning in warnings:
            event = WARNING_EVENTS.get(warning if isinstance(warning, str) else "")
            if event is None:
                continue
            component, outcome = event
            series.component_events[component][outcome] += 1
            if component == "citation_validator" and outcome == "failed":
                series.citation_validation_failure_count += 1

    def _record_durations(
        self,
        series: _MetricSeries,
        stage_durations_ms: Mapping[str, object] | None,
    ) -> None:
        if not isinstance(stage_durations_ms, Mapping):
            return
        for stage in ALLOWED_STAGES:
            duration = normalize_duration(stage_durations_ms.get(stage))
            if duration is None:
                continue
            samples = series.durations_ms.setdefault(
                stage,
                deque(maxlen=self._sample_limit),
            )
            samples.append(duration)


def _serialize_series(series: _MetricSeries) -> dict[str, Any]:
    return {
        "pipeline_mode": series.mode,
        "pipeline_version": series.pipeline_version,
        "execution_count": series.execution_count,
        "degraded_count": series.degraded_count,
        "citation_validation_failure_count": series.citation_validation_failure_count,
        "answer_status_counts": {
            status: series.answer_status_counts.get(status, 0)
            for status in sorted(ALLOWED_ANSWER_STATUSES)
        },
        "component_events": {
            component: {
                outcome: series.component_events[component].get(outcome, 0)
                for outcome in sorted(ALLOWED_OUTCOMES)
            }
            for component in ALLOWED_COMPONENTS
        },
        "durations_ms": {
            stage: duration_summary(samples)
            for stage, samples in sorted(series.durations_ms.items())
        },
    }


__all__ = ["RagRuntimeMetrics"]
