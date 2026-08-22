# -*- coding: utf-8 -*-
"""真实 RAG pipeline 的离线评测适配器。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from time import perf_counter
from typing import Any

from app.config import Config, rag_pipeline_config_snapshot

from .contracts import CitationManifest, EvidenceReference, RagExecutionRequest
from .evaluation_contracts import EvaluationCase, EvaluationExecution, EvaluationPipeline


def build_runtime_executor(*, pipeline: EvaluationPipeline, corpus_version: str):
    """显式选择 legacy 或 v2；调用时才接触 Qdrant、Embedding、Reranker 和 LLM。"""
    if pipeline not in {"legacy", "v2"}:
        raise ValueError("pipeline must be 'legacy' or 'v2'")
    corpus = corpus_version.strip()
    if not corpus:
        raise ValueError("corpus_version is required")

    from app.services.enhanced_rag_engine import get_rag_engine

    engine = get_rag_engine()
    fingerprint = evaluation_config_fingerprint()
    if pipeline == "v2":
        rag_pipeline = engine._enterprise_rag_pipeline()

        def execute(case: EvaluationCase) -> EvaluationExecution:
            started_at = perf_counter()
            result = rag_pipeline.execute(
                RagExecutionRequest(
                    query=_case_query(case),
                    request_id=f"eval-{case.case_id}",
                    use_rerank=True,
                )
            )
            stages = result.trace.stage_summary
            candidate_entries = _mapping_sequence(_mapping_value(stages, "candidate", "candidates"))
            return EvaluationExecution(
                candidate_document_ids=tuple(
                    str(item.get("document_id")).strip()
                    for item in candidate_entries
                    if item.get("document_id") is not None and str(item.get("document_id")).strip()
                ),
                evidence_references=result.citations.references,
                citation_manifest=result.citations,
                answer_status=result.answer_status,
                status_observable=True,
                citation_observable=True,
                pipeline_version_key=result.trace.pipeline_version_key,
                corpus_version=corpus,
                config_fingerprint=fingerprint,
                retrieval_ms=_non_negative_int(result.trace.retrieval_ms) or max(0, round((perf_counter() - started_at) * 1000)),
                rerank_ms=_mapping_int(stages, "rerank", "elapsed_ms"),
                evidence_token_count=_mapping_int(stages, "evidence", "token_count"),
                evidence_token_budget=_mapping_int(stages, "evidence", "token_budget"),
            )

        return execute

    def execute_legacy(case: EvaluationCase) -> EvaluationExecution:
        started_at = perf_counter()
        query = _case_query(case)
        candidates = engine.retrieve(query, top_k=40)
        legacy_result = engine._ask_legacy(query, use_rerank=True)
        references = tuple(
            _legacy_reference(source, index)
            for index, source in enumerate(legacy_result.get("sources") or (), start=1)
            if isinstance(source, Mapping)
        )
        return EvaluationExecution(
            candidate_document_ids=tuple(
                str(document.get("id")).strip()
                for document in candidates
                if isinstance(document, Mapping) and document.get("id") is not None and str(document.get("id")).strip()
            ),
            evidence_references=references,
            citation_manifest=CitationManifest(references=references),
            answer_status=None,
            status_observable=False,
            citation_observable=False,
            pipeline_version_key="legacy-enhanced-rag-v1",
            corpus_version=corpus,
            config_fingerprint=fingerprint,
            retrieval_ms=max(0, round((perf_counter() - started_at) * 1000)),
        )

    return execute_legacy


def evaluation_case_from_model(model: Any) -> EvaluationCase:
    """兼容历史 ORM 的 JSON 字段，query 仅保留在内存执行对象。"""
    return EvaluationCase(
        case_id=int(model.id),
        case_key=f"db-{int(model.id)}",
        category=_text(getattr(model, "category", None), "uncategorized"),
        difficulty=_text(getattr(model, "difficulty", None), "medium"),
        expected_document_ids=_json_ids(getattr(model, "expected_doc_ids", None)),
        expected_status=_text(getattr(model, "expected_status", None), "supported"),
        review_note=_text(getattr(model, "notes", None), "database-label"),
        query=_text(getattr(model, "query", None), ""),
        expected_evidence=_json_evidence(getattr(model, "expected_evidence_json", None)),
        tags=_json_tags(getattr(model, "expected_evidence_json", None)),
    )


def _json_evidence(value: object) -> tuple[dict, ...]:
    """从 expected_evidence_json 解析富证据标签；仅保留受控字段，丢弃正文/Prompt。"""
    parsed = _coerce_json_list(value)
    allowed = {
        "document_id",
        "title",
        "chunk_id",
        "start_line",
        "end_line",
        "corpus_version",
        "role",
    }
    cleaned: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        cleaned.append({key: item[key] for key in allowed if key in item})
    return tuple(cleaned)


def _json_tags(value: object) -> tuple[str, ...]:
    """从 expected_evidence_json 的 tags 字段解析标签（若存在）。"""
    parsed = _coerce_json_list(value)
    if not parsed:
        return ()
    tags: list[str] = []
    for item in parsed:
        if isinstance(item, dict) and isinstance(item.get("tags"), list):
            for tag in item["tags"]:
                if isinstance(tag, str) and tag.strip() and tag not in tags:
                    tags.append(tag.strip())
    return tuple(tags)


def _coerce_json_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    else:
        parsed = value
    return parsed if isinstance(parsed, list) else []


def evaluation_config_fingerprint() -> str:
    """仅由非敏感配置和模型标识生成可比较指纹。"""
    payload = {
        "pipeline": rag_pipeline_config_snapshot(),
        "embedding_model": Config.EMBEDDING_API_MODEL if Config.EMBEDDING_API_ENABLED else Config.EMBEDDING_MODEL,
        "reranker_model": Config.RERANKER_API_MODEL if Config.RERANKER_API_ENABLED else Config.RERANKER_MODEL,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _case_query(case: EvaluationCase) -> str:
    query = case.query.strip()
    if not query:
        raise ValueError("evaluation case query is unavailable")
    return query


def _mapping_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _mapping_value(mapping: object, key: str, nested_key: str) -> object:
    nested = mapping.get(key) if isinstance(mapping, Mapping) else None
    return nested.get(nested_key) if isinstance(nested, Mapping) else None


def _mapping_int(mapping: object, key: str, nested_key: str) -> int | None:
    return _non_negative_int(_mapping_value(mapping, key, nested_key))


def _legacy_reference(source: Mapping[str, Any], index: int) -> EvidenceReference:
    return EvidenceReference(
        citation_id=f"C{index}",
        document_id=str(source.get("document_id") or source.get("doc_id") or source.get("id") or f"legacy-{index}"),
        title=_text(source.get("title"), "untitled"),
        source=_optional_text(source.get("source")),
        start_line=_non_negative_int(source.get("start_line")),
        end_line=_non_negative_int(source.get("end_line")),
    )


def _json_ids(value: object) -> tuple[str, ...]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ()
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in parsed if item is not None and not isinstance(item, bool) and str(item).strip())


def _text(value: object, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _optional_text(value: object) -> str | None:
    text = _text(value, "")
    return text or None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


__all__ = ["build_runtime_executor", "evaluation_case_from_model", "evaluation_config_fingerprint"]