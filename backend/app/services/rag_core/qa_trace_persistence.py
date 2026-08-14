# -*- coding: utf-8 -*-
"""QA 回答完成后的 RAG trace 受控落库与 pipeline version 关联。"""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from app import db
from app.config import Config, rag_pipeline_config_snapshot
from app.models.qa import QARecord, RagPipelineVersion
from app.services.rag_core.contracts import RetrievalTrace
from app.services.rag_core.trace_recorder import TraceRecorder

logger = logging.getLogger(__name__)


def persist_trace_for_qa_record(
    *,
    user_id: int,
    record: QARecord,
    result: Mapping[str, Any],
) -> int | None:
    """把安全 retrieval summary 关联到已提交 QA 记录；任一失败都不阻断回答。"""
    trace = _trace_from_result(result)
    if trace is None:
        return None

    try:
        pipeline_version_id = _ensure_pipeline_version(trace)
        trace_id = TraceRecorder(session=db.session).try_record(
            user_id=user_id,
            trace=trace,
            record_id=record.id,
            pipeline_version_id=pipeline_version_id,
            stage="trace_persistence",
        )
        if trace_id is None:
            return None
        record.rag_trace_id = trace_id
        db.session.commit()
        return trace_id
    except Exception as exc:  # noqa: BLE001 诊断数据失败不得影响已生成回答
        db.session.rollback()
        logger.warning(
            "RAG trace link failed stage=trace_persistence request_id=%s error_type=%s",
            _safe_identifier(trace.request_id) or "unknown",
            type(exc).__name__,
        )
        return None


def _trace_from_result(result: Mapping[str, Any]) -> RetrievalTrace | None:
    """只从 RAG Core 的脱敏 summary 重建 trace，拒绝缺失或畸形数据。"""
    summary = result.get("retrieval_summary")
    if not isinstance(summary, Mapping):
        return None
    stage_summary = summary.get("stage_summary")
    if not isinstance(stage_summary, Mapping):
        return None
    query_fingerprint = _safe_identifier(summary.get("query_fingerprint"))
    pipeline_version_key = _safe_identifier(
        summary.get("pipeline_version_key") or result.get("pipeline_version"),
    )
    if not query_fingerprint or not pipeline_version_key:
        return None
    return RetrievalTrace(
        request_id=_safe_identifier(summary.get("request_id")),
        query_fingerprint=query_fingerprint,
        pipeline_version_key=pipeline_version_key,
        stage_summary=dict(stage_summary),
        warnings=_safe_warnings(summary.get("warnings")),
        retrieval_ms=_safe_non_negative_int(summary.get("retrieval_ms")),
    )


def _ensure_pipeline_version(trace: RetrievalTrace) -> int:
    """按稳定版本键幂等登记运行快照，避免将用户数据写入配置快照。"""
    existing = RagPipelineVersion.query.filter_by(
        version_key=trace.pipeline_version_key,
    ).first()
    if existing is not None:
        return int(existing.id)

    prompt_version = (
        "citation-json-v1"
        if "candidate" in trace.stage_summary
        else "legacy-enhanced-rag-v1"
    )
    embedding_version = (
        Config.EMBEDDING_API_MODEL
        if Config.EMBEDDING_API_ENABLED
        else Config.EMBEDDING_MODEL
    )
    reranker_version = (
        Config.RERANKER_API_MODEL
        if Config.RERANKER_API_ENABLED
        else Config.RERANKER_MODEL
    )
    pipeline_version = RagPipelineVersion(
        version_key=trace.pipeline_version_key,
        config_json=rag_pipeline_config_snapshot(),
        prompt_version=prompt_version,
        embedding_version=embedding_version,
        reranker_version=reranker_version,
    )
    db.session.add(pipeline_version)
    db.session.flush()
    return int(pipeline_version.id)


def _safe_identifier(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized[:64] or None


def _safe_warnings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    warnings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        warning = item.strip()
        if warning and warning not in warnings:
            warnings.append(warning[:128])
    return tuple(warnings)


def _safe_non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = ["persist_trace_for_qa_record"]