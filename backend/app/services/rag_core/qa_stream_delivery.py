# -*- coding: utf-8 -*-
"""QA SSE 终态的受限序列化与降级结果构造。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.qa import QARecord
from app.services.rag_core.qa_record_payload import rag_core_response_fields

_ALLOWED_ANSWER_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "degraded",
}


def build_interrupted_stream_result() -> dict[str, Any]:
    """构造不泄漏内部异常的 RAG 流中断结果。"""
    return {
        "answer": "当前检索或生成链路暂不可用，无法提供可核验回答。请稍后重试。",
        "reasoning": None,
        "sources": [],
        "retrieved_docs": [],
        "confidence": 0.0,
        "response_time": None,
        "answer_status": "degraded",
        "citations": {
            "citations": [],
            "claim_citations": {},
        },
        "rag_warnings": ["RAG_STREAM_INTERRUPTED"],
        "warning_code": "RAG_STREAM_INTERRUPTED",
    }


def add_rag_warning(
    result: Mapping[str, Any],
    warning_code: str,
) -> dict[str, Any]:
    """复制终态结果并追加一次受控 warning code。"""
    payload = dict(result)
    warnings = [
        str(item).strip()
        for item in payload.get("rag_warnings") or []
        if isinstance(item, str) and item.strip()
    ]
    if warning_code not in warnings:
        warnings.append(warning_code)
    payload["rag_warnings"] = warnings
    if payload.get("answer_status") not in _ALLOWED_ANSWER_STATUSES:
        payload["answer_status"] = "degraded"
    return payload


def build_stream_done_payload(
    result: Mapping[str, Any],
    *,
    record: QARecord | None,
    conversation_id: int | None,
    attachments: list[dict[str, Any]],
) -> dict[str, Any]:
    """构造客户端可直接渲染的 done 事件，不透传内部异常或原始响应。"""
    payload = dict(result)
    sources = payload.get("retrieved_docs") or payload.get("sources") or []
    if not isinstance(sources, list):
        sources = []

    response_fields = _response_fields_for_record(record, payload)
    return {
        "id": record.id if record is not None else None,
        "conversation_id": conversation_id,
        "answer": _safe_text(payload.get("answer")),
        "reasoning": _safe_text(payload.get("reasoning")),
        "sources": sources,
        "confidence": _safe_number(payload.get("confidence")),
        "response_time": _safe_number(payload.get("response_time")),
        "attachments": attachments,
        "memory_changes": {
            "added": 0,
            "updated": 0,
            "skipped": 0,
        },
        "created_at": record.created_at.isoformat() if record and record.created_at else None,
        "warning_code": _safe_text(payload.get("warning_code")),
        "rag_warnings": _safe_warnings(payload.get("rag_warnings")),
        "model_name": _safe_text(payload.get("model_name")),
        "provider": _safe_text(payload.get("provider")),
        "model_version": _safe_text(payload.get("model_version")),
        **response_fields,
    }


def _response_fields_for_record(
    record: QARecord | None,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    if record is not None:
        return rag_core_response_fields(record, result)

    answer_status = result.get("answer_status")
    if answer_status not in _ALLOWED_ANSWER_STATUSES:
        answer_status = "degraded"
    citations = result.get("citations")
    if not isinstance(citations, (dict, list)):
        citations = {
            "citations": [],
            "claim_citations": {},
        }
    pipeline_version = result.get("pipeline_version")
    if not isinstance(pipeline_version, str) or not pipeline_version.strip():
        pipeline_version = None
    retrieval_summary = result.get("retrieval_summary")
    if not isinstance(retrieval_summary, dict):
        retrieval_summary = None
    return {
        "answer_status": answer_status,
        "citations": citations,
        "trace_id": None,
        "pipeline_version": pipeline_version,
        "retrieval_summary": retrieval_summary,
    }


def _safe_warnings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    warnings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized and normalized not in warnings:
            warnings.append(normalized[:128])
    return warnings


def _safe_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_number(value: object) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "add_rag_warning",
    "build_interrupted_stream_result",
    "build_stream_done_payload",
]