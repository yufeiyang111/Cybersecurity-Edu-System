# -*- coding: utf-8 -*-
"""RAG 脱敏 trace 持久化：仅保存阶段摘要，不保存原文内容。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from typing import Any

from app.models.qa import RagRetrievalTrace
from app.services.rag_core.contracts import RetrievalTrace
from app.services.rag_core.metrics import RagRuntimeMetrics

logger = logging.getLogger(__name__)

_FORBIDDEN_TRACE_KEYS = {
    "answer",
    "authorization",
    "content",
    "document",
    "documents",
    "parent_text",
    "prompt",
    "query",
    "reasoning",
    "retrieved_docs",
    "source_text",
    "sources",
    "text",
}


class TraceRecorder:
    """将 RetrievalTrace 写为脱敏 ORM 记录，不负责提交外层事务。"""

    def __init__(
        self,
        *,
        session,
        metrics: RagRuntimeMetrics | None = None,
    ) -> None:
        self._session = session
        self._metrics = metrics

    def record(
        self,
        *,
        user_id: int,
        trace: RetrievalTrace,
        record_id: int | None = None,
        pipeline_version_id: int | None = None,
    ) -> int:
        """写入脱敏 trace 并返回 ID；调用方决定事务何时 commit。"""
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            raise ValueError("user_id must be a positive integer")
        stage_summary, redacted = redact_stage_summary(trace.stage_summary)
        warnings = _safe_warnings(trace.warnings)
        if redacted and "TRACE_SENSITIVE_FIELD_REDACTED" not in warnings:
            warnings.append("TRACE_SENSITIVE_FIELD_REDACTED")
        row = RagRetrievalTrace(
            request_id=_safe_identifier(trace.request_id),
            record_id=_positive_or_none(record_id),
            user_id=user_id,
            pipeline_version_id=_positive_or_none(pipeline_version_id),
            query_fingerprint=_required_fingerprint(trace.query_fingerprint),
            stage_summary_json=stage_summary,
            warnings_json=warnings or None,
            retrieval_ms=max(0, int(trace.retrieval_ms)),
        )
        self._session.add(row)
        self._session.flush()
        return int(row.id)

    def try_record(
        self,
        *,
        user_id: int,
        trace: RetrievalTrace,
        record_id: int | None = None,
        pipeline_version_id: int | None = None,
        stage: str = "trace_persistence",
    ) -> int | None:
        """安全尝试写入 trace；失败时回滚本次 trace 事务但不阻断主回答。"""
        try:
            return self.record(
                user_id=user_id,
                trace=trace,
                record_id=record_id,
                pipeline_version_id=pipeline_version_id,
            )
        except Exception as exc:  # noqa: BLE001 需要隔离诊断写入故障
            self._session.rollback()
            self._record_trace_failure(trace)
            logger.warning(
                "RAG trace persistence failed stage=%s request_id=%s error_type=%s",
                _safe_stage(stage),
                _safe_identifier(trace.request_id) or "unknown",
                type(exc).__name__,
            )
            return None

    def _record_trace_failure(self, trace: RetrievalTrace) -> None:
        """记录 trace DB 失败计数，观测器异常不得影响原始降级路径。"""
        if self._metrics is None:
            return
        try:
            pipeline_version = _safe_identifier(trace.pipeline_version_key) or "unknown"
            pipeline_mode = "v2" if pipeline_version.startswith("rag-v2-") else "legacy"
            self._metrics.record_component_event(
                component="trace_db",
                outcome="failed",
                pipeline_mode=pipeline_mode,
                pipeline_version=pipeline_version,
            )
        except Exception:
            return


def redact_stage_summary(summary: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """递归移除敏感字段；返回安全摘要及是否发生剔除。"""
    redacted = False

    def sanitize(value: object) -> object:
        nonlocal redacted
        if isinstance(value, Mapping):
            output: dict[str, Any] = {}
            for raw_key, raw_value in value.items():
                key = str(raw_key)
                if key.strip().lower() in _FORBIDDEN_TRACE_KEYS:
                    redacted = True
                    continue
                output[key] = sanitize(raw_value)
            return output
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [sanitize(item) for item in value]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:128]
        return str(value)[:128]

    if not isinstance(summary, Mapping):
        return {}, True
    sanitized = sanitize(summary)
    return dict(sanitized), redacted


def _safe_warnings(warnings: Sequence[object]) -> list[str]:
    output: list[str] = []
    for warning in warnings:
        if not isinstance(warning, str):
            continue
        normalized = warning.strip()
        if normalized and normalized not in output:
            output.append(normalized[:128])
    return output


def _safe_stage(value: object) -> str:
    """日志阶段仅保留受控短标识，避免把外部文本写入日志。"""
    normalized = str(value or "").strip().lower()
    return normalized[:64] if normalized.replace("_", "").replace("-", "").isalnum() else "unknown"


def _safe_identifier(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized[:64] or None


def _positive_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _required_fingerprint(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("query_fingerprint is required")
    return normalized[:64]


__all__ = ["TraceRecorder", "redact_stage_summary"]
