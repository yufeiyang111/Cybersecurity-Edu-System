# -*- coding: utf-8 -*-
"""QA 路由使用的 RAG Core 持久化字段与受限响应序列化。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.qa import QARecord
from app.services.rag_core.citation_evidence import build_evidence_details

_ALLOWED_ANSWER_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "ungrounded",
    "degraded",
}


def rag_core_record_fields(result: Mapping[str, Any]) -> dict[str, Any]:
    """归一化可持久化元数据，拒绝未知状态和非 JSON citation manifest。"""
    answer_status = result.get("answer_status")
    if answer_status not in _ALLOWED_ANSWER_STATUSES:
        answer_status = None

    citation_manifest = result.get("citations")
    if not isinstance(citation_manifest, (dict, list)):
        citation_manifest = None

    trace_id = _positive_int_or_none(result.get("trace_id"))
    pipeline_version = _identifier_or_none(result.get("pipeline_version"))
    if pipeline_version and citation_manifest is None:
        answer_status = "degraded"

    return {
        "answer_status": answer_status,
        "citation_manifest_json": citation_manifest,
        "rag_trace_id": trace_id,
        "pipeline_version_key": pipeline_version,
    }


def rag_core_response_fields(
    record: QARecord,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """返回旧客户端可忽略的 v2 字段，不暴露未经验证的结果元数据。"""
    retrieval_summary = result.get("retrieval_summary")
    if not isinstance(retrieval_summary, dict):
        retrieval_summary = None
    return {
        "answer_status": record.answer_status,
        "citations": record.citation_manifest_json,
        "trace_id": record.rag_trace_id,
        "pipeline_version": record.pipeline_version_key,
        "retrieval_summary": retrieval_summary,
    }


def evidence_payload(record: QARecord) -> dict[str, Any]:
    """构造本人可读的 citation manifest 与摘要，刻意不返回答案/CoT/原始资料。"""
    manifest = record.citation_manifest_json
    if isinstance(manifest, list):
        manifest = {
            "citations": manifest,
            "claim_citations": {},
        }
    elif not isinstance(manifest, dict):
        manifest = {
            "citations": [],
            "claim_citations": {},
        }
    citations = manifest.get("citations")
    citation_count = len(citations) if isinstance(citations, list) else 0
    detail_payload = build_evidence_details(record, manifest)
    return {
        "record_id": record.id,
        "answer_status": record.answer_status,
        "citations": manifest,
        "citation_count": citation_count,
        "trace_id": record.rag_trace_id,
        "pipeline_version": record.pipeline_version_key,
        **detail_payload,
    }


def _positive_int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _identifier_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:64] or None


__all__ = [
    "evidence_payload",
    "rag_core_record_fields",
    "rag_core_response_fields",
]
