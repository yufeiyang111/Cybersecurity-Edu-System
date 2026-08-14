# -*- coding: utf-8 -*-
"""公共 RAG 执行结果组装：回答契约、兼容载荷与脱敏 trace 集中在此。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.services.rag_core.answer_composer import AnswerComposition
from app.services.rag_core.contracts import (
    CitationManifest,
    RagExecutionRequest,
    RagExecutionResult,
    RetrievalTrace,
)
from app.services.rag_core.pipeline import query_fingerprint
from app.services.rag_core.rerank_stage import RerankResult


@dataclass(frozen=True)
class ProviderGeneration:
    """Provider 生成结果的受控适配；原始响应只在内存中交给 AnswerComposer。"""

    raw_response: str
    reasoning: str | None = None
    confidence: float | None = None
    model_name: str | None = None
    provider: str | None = None
    model_version: str | None = None
    response_time: float | None = None
    warning_code: str | None = None


def composed_result(
    *,
    request: RagExecutionRequest,
    pipeline_version_key: str,
    composition: AnswerComposition,
    generation: ProviderGeneration,
    warnings: tuple[str, ...],
    trace_stages: dict[str, Any],
    retrieval_ms: int,
) -> RagExecutionResult:
    """将验证后的结构化回答映射为统一 RAG 结果和兼容响应载荷。"""
    trace_stages["answer"] = {
        "answer_status": composition.answer_status,
        "citation_count": len(composition.citations.references),
        "claim_count": len(composition.claims),
        "uncertainty_count": len(composition.uncertainty),
        "warning_count": len(warnings),
    }
    return RagExecutionResult(
        answer=composition.answer,
        answer_status=composition.answer_status,
        citations=composition.citations,
        trace=_trace(
            request=request,
            pipeline_version_key=pipeline_version_key,
            stage_summary=trace_stages,
            warnings=warnings,
            retrieval_ms=retrieval_ms,
        ),
        confidence=_finite_float(generation.confidence),
        model_name=_text_or_none(generation.model_name),
        provider=_text_or_none(generation.provider),
        model_version=_text_or_none(generation.model_version),
        response_time=_non_negative_float(generation.response_time),
        rag_warnings=warnings,
        reasoning=_text_or_none(generation.reasoning),
        compatibility_payload=_compatibility_payload(
            composition.citations,
            composition.uncertainty,
        ),
    )


def terminal_result(
    *,
    request: RagExecutionRequest,
    pipeline_version_key: str,
    answer: str,
    answer_status: str,
    citations: CitationManifest,
    warnings: tuple[str, ...],
    trace_stages: dict[str, Any],
    retrieval_ms: int,
) -> RagExecutionResult:
    """构造不足证据或依赖失败结果；不调用 Provider、不伪造引用。"""
    trace_stages["answer"] = {
        "answer_status": answer_status,
        "citation_count": len(citations.references),
        "claim_count": 0,
        "uncertainty_count": 1,
        "warning_count": len(warnings),
    }
    return RagExecutionResult(
        answer=answer,
        answer_status=answer_status,
        citations=citations,
        trace=_trace(
            request=request,
            pipeline_version_key=pipeline_version_key,
            stage_summary=trace_stages,
            warnings=warnings,
            retrieval_ms=retrieval_ms,
        ),
        rag_warnings=warnings,
        compatibility_payload={
            "retrieved_docs": [],
            "sources": [],
            "uncertainty": [answer],
        },
    )


def unique_warnings(*groups: Sequence[str]) -> tuple[str, ...]:
    """去重、限长并仅保留安全 warning code。"""
    warnings: list[str] = []
    for group in groups:
        for warning in group:
            if not isinstance(warning, str):
                continue
            normalized = warning.strip()
            if normalized and normalized not in warnings:
                warnings.append(normalized[:128])
    return tuple(warnings)


def rerank_warnings(result: RerankResult) -> tuple[str, ...]:
    """把 rerank 状态映射为稳定 warning code。"""
    if result.status == "failed":
        return ("RERANK_FAILED",)
    if result.status == "skipped" and result.failure_type not in {"empty_candidates", "disabled"}:
        return ("RERANK_SKIPPED",)
    return ()


def generation_warnings(generation: ProviderGeneration) -> tuple[str, ...]:
    """保留 Provider 已规范化的 warning code。"""
    warning = _text_or_none(generation.warning_code)
    return (warning,) if warning else ()


def _trace(
    *,
    request: RagExecutionRequest,
    pipeline_version_key: str,
    stage_summary: Mapping[str, Any],
    warnings: tuple[str, ...],
    retrieval_ms: int,
) -> RetrievalTrace:
    return RetrievalTrace(
        request_id=request.request_id,
        query_fingerprint=query_fingerprint(request.query),
        pipeline_version_key=pipeline_version_key,
        stage_summary=stage_summary,
        warnings=warnings,
        retrieval_ms=retrieval_ms,
    )


def _compatibility_payload(
    citations: CitationManifest,
    uncertainty: Sequence[str],
) -> dict[str, Any]:
    source_payload = [
        reference.to_manifest_dict()
        for reference in citations.references
    ]
    return {
        "retrieved_docs": source_payload,
        "sources": source_payload,
        "uncertainty": list(uncertainty),
    }


def _text_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _non_negative_float(value: object) -> float | None:
    number = _finite_float(value)
    return number if number is not None and number >= 0 else None


__all__ = [
    "ProviderGeneration",
    "composed_result",
    "generation_warnings",
    "rerank_warnings",
    "terminal_result",
    "unique_warnings",
]