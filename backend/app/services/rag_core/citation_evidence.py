# -*- coding: utf-8 -*-
"""为 QA 记录构造受控 citation 详情，不让前端推测知识文档标识。"""
from __future__ import annotations

import html
import math
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.models.knowledge import KnowledgeItem
from app.models.qa import QARecord


MAX_CITATION_DETAILS = 12
MAX_PREVIEW_CHARS = 480
_HTML_TAG_PATTERN = re.compile(r"<[^>]*>")
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def build_evidence_details(record: QARecord, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """构造 record 所属用户可查看的 citation 详情和检索辅助信号。"""
    citations = _citation_entries(manifest)
    claim_counts = _claim_counts(manifest)
    document_ids = {
        document_id
        for citation in citations
        if (document_id := _positive_int(citation.get("document_id"))) is not None
    }
    documents = _published_documents_by_id(document_ids)

    details = []
    for citation in citations[:MAX_CITATION_DETAILS]:
        detail = _citation_detail(
            citation=citation,
            document=documents.get(_positive_int(citation.get("document_id"))),
            claim_count=claim_counts.get(citation["citation_id"], 0),
        )
        details.append(detail)

    return {
        "citation_details": details,
        "citation_details_truncated": len(citations) > MAX_CITATION_DETAILS,
        "retrieval_signal": build_retrieval_signal(record.confidence),
    }


def build_retrieval_signal(confidence: object) -> dict[str, Any]:
    """把未校准检索启发式映射为非概率的辅助等级。"""
    value = _normalized_confidence(confidence)
    if value is None:
        return {
            "level": "unavailable",
            "is_calibrated": False,
        }
    if value >= 0.75:
        level = "high"
    elif value >= 0.45:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "is_calibrated": False,
    }


def _citation_entries(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_citations = manifest.get("citations")
    if not isinstance(raw_citations, list):
        return []

    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in raw_citations:
        if not isinstance(item, Mapping):
            continue
        citation_id = _short_text(item.get("citation_id"), max_length=128)
        if not citation_id or citation_id in seen_ids:
            continue
        seen_ids.add(citation_id)
        entries.append(
            {
                "citation_id": citation_id,
                "document_id": item.get("document_id"),
                "title": _short_text(item.get("title"), max_length=300),
                "title_path": _short_text(item.get("title_path"), max_length=500),
                "source": _short_text(item.get("source"), max_length=300),
                "start_line": _positive_int(item.get("start_line")),
                "end_line": _positive_int(item.get("end_line")),
                "corpus_version": _short_text(item.get("corpus_version"), max_length=128),
            }
        )
    return entries


def _claim_counts(manifest: Mapping[str, Any]) -> Counter[str]:
    raw_claims = manifest.get("claim_citations")
    if not isinstance(raw_claims, Mapping):
        return Counter()

    counts: Counter[str] = Counter()
    for citation_ids in raw_claims.values():
        if not isinstance(citation_ids, list):
            continue
        claim_ids = {
            _short_text(citation_id, max_length=128)
            for citation_id in citation_ids
            if _short_text(citation_id, max_length=128)
        }
        counts.update(claim_ids)
    return counts


def _published_documents_by_id(document_ids: set[int]) -> dict[int, KnowledgeItem]:
    if not document_ids:
        return {}
    documents = (
        KnowledgeItem.query
        .filter(
            KnowledgeItem.id.in_(document_ids),
            KnowledgeItem.status == "published",
        )
        .all()
    )
    return {document.id: document for document in documents}


def _citation_detail(
    *,
    citation: Mapping[str, Any],
    document: KnowledgeItem | None,
    claim_count: int,
) -> dict[str, Any]:
    detail = {
        "citation_id": citation["citation_id"],
        "title": citation.get("title") or "未命名资料",
        "title_path": citation.get("title_path"),
        "source": citation.get("source"),
        "start_line": citation.get("start_line"),
        "end_line": citation.get("end_line"),
        "corpus_version": citation.get("corpus_version"),
        "claim_count": claim_count,
        "document": None,
        "preview": None,
    }
    if document is None:
        return detail

    detail["document"] = {
        "type": "public_knowledge",
        "knowledge_id": document.id,
    }
    detail["preview"] = _preview_for_lines(
        content=document.content,
        start_line=citation.get("start_line"),
        end_line=citation.get("end_line"),
    )
    return detail


def _preview_for_lines(
    *,
    content: object,
    start_line: object,
    end_line: object,
) -> dict[str, Any] | None:
    if not isinstance(content, str) or not content.strip():
        return None
    start = _positive_int(start_line)
    end = _positive_int(end_line)
    if start is None or end is None or end < start:
        return None

    lines = content.splitlines()
    if start > len(lines):
        return None
    actual_end = min(end, len(lines))
    normalized = _safe_preview_text("\n".join(lines[start - 1:actual_end]))
    if not normalized:
        return None

    is_truncated = len(normalized) > MAX_PREVIEW_CHARS or actual_end < end
    return {
        "text": normalized[:MAX_PREVIEW_CHARS],
        "start_line": start,
        "end_line": actual_end,
        "is_truncated": is_truncated,
    }


def _safe_preview_text(value: str) -> str:
    without_html = _HTML_TAG_PATTERN.sub("", html.unescape(value))
    without_controls = _CONTROL_CHARACTER_PATTERN.sub(" ", without_html)
    return _WHITESPACE_PATTERN.sub(" ", without_controls).strip()


def _normalized_confidence(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(normalized) or normalized < 0 or normalized > 1:
        return None
    return normalized


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized.isdecimal():
        return None
    parsed = int(normalized)
    return parsed if parsed > 0 else None


def _short_text(value: object, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:max_length] or None