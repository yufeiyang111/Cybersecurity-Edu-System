# -*- coding: utf-8 -*-
"""企业 RAG 管道入口与 legacy 兼容适配器。"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping
from typing import Any

from .contracts import (
    CitationManifest,
    EvidenceReference,
    RagExecutionRequest,
    RagExecutionResult,
    RetrievalTrace,
)

RagExecutor = Callable[[RagExecutionRequest], RagExecutionResult]
RagStreamer = Callable[[RagExecutionRequest], Iterator[dict[str, Any]]]
LegacyAsk = Callable[..., dict[str, Any]]
LegacyStream = Callable[..., Iterator[dict[str, Any]]]


def build_pipeline_version_key(
    *,
    config: Mapping[str, bool | int | str],
    prompt_version: str,
    embedding_version: str,
    reranker_version: str,
) -> str:
    """基于非敏感配置和模型版本生成稳定指纹，不接收用户请求数据。"""
    payload = {
        "config": dict(sorted(config.items())),
        "prompt_version": prompt_version,
        "embedding_version": embedding_version,
        "reranker_version": reranker_version,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"rag-v2-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def query_fingerprint(query: str) -> str:
    """生成 query 指纹，供 trace 关联而不保存原 query。"""
    normalized = " ".join(query.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class EnterpriseRagPipeline:
    """RAG Core 的唯一执行入口；具体阶段将在后续任务中注入此入口。"""

    def __init__(
        self,
        executor: RagExecutor,
        streamer: RagStreamer | None = None,
    ) -> None:
        self._executor = executor
        self._streamer = streamer

    def execute(self, request: RagExecutionRequest) -> RagExecutionResult:
        """执行非流式管道并校验阶段实现返回统一契约。"""
        result = self._executor(request)
        if not isinstance(result, RagExecutionResult):
            raise TypeError("RAG pipeline executor must return RagExecutionResult")
        return result

    def stream(self, request: RagExecutionRequest) -> Iterator[dict[str, Any]]:
        """执行流式管道；没有独立 stream 实现时降级为单个 done 事件。"""
        if self._streamer is not None:
            yield from self._streamer(request)
            return
        result = self.execute(request)
        if result.reasoning:
            yield {"type": "reasoning", "delta": result.reasoning}
        if result.answer:
            yield {"type": "delta", "content": result.answer}
        yield {"type": "done", **result.to_legacy_payload()}


class LegacyRagAdapter:
    """将现有 EnhancedRAGEngine 的响应映射到 RAG Core 契约，保证灰度期开关可回退。"""

    def __init__(
        self,
        *,
        legacy_ask: LegacyAsk,
        legacy_stream: LegacyStream,
        pipeline_version_key: str,
    ) -> None:
        self._legacy_ask = legacy_ask
        self._legacy_stream = legacy_stream
        self._pipeline_version_key = pipeline_version_key

    def execute(self, request: RagExecutionRequest) -> RagExecutionResult:
        """调用 legacy 非流式链路，再以结构化结果返回。"""
        result = self._legacy_ask(**self._legacy_kwargs(request))
        return self._to_result(request, result)

    def stream(self, request: RagExecutionRequest) -> Iterator[dict[str, Any]]:
        """转发 legacy SSE 事件，只在 done 事件附加 v2 元数据。"""
        for event in self._legacy_stream(**self._legacy_kwargs(request)):
            if event.get("type") != "done":
                yield event
                continue
            execution_result = self._to_result(request, event)
            yield {
                **event,
                **execution_result.to_legacy_payload(),
            }

    def _legacy_kwargs(self, request: RagExecutionRequest) -> dict[str, Any]:
        return {
            "query": request.query,
            "conversation_history": list(request.conversation_history) or None,
            "use_rerank": request.use_rerank,
            "user_preferences": dict(request.user_preferences) if request.user_preferences else None,
            "user_id": request.user_id,
            "memories": list(request.memories) or None,
        }

    def _to_result(
        self,
        request: RagExecutionRequest,
        legacy_result: Mapping[str, Any],
    ) -> RagExecutionResult:
        sources = legacy_result.get("sources") or []
        references = tuple(
            _evidence_reference_from_legacy(source, index)
            for index, source in enumerate(sources, start=1)
            if isinstance(source, Mapping)
        )
        retrieved_docs = legacy_result.get("retrieved_docs") or []
        warnings = tuple(
            str(warning)
            for warning in legacy_result.get("rag_warnings") or []
            if isinstance(warning, str)
        )
        trace = RetrievalTrace(
            request_id=request.request_id,
            query_fingerprint=query_fingerprint(request.query),
            pipeline_version_key=self._pipeline_version_key,
            stage_summary={
                "adapter": "legacy",
                "retrieved_document_count": len(retrieved_docs),
                "citation_count": len(references),
            },
            warnings=warnings,
            retrieval_ms=0,
        )
        return RagExecutionResult(
            answer=str(legacy_result.get("answer") or ""),
            answer_status="degraded",
            citations=CitationManifest(references=references),
            trace=trace,
            confidence=_optional_float(legacy_result.get("confidence")),
            model_name=_optional_text(legacy_result.get("model_name")),
            provider=_optional_text(legacy_result.get("provider")),
            model_version=_optional_text(legacy_result.get("model_version")),
            response_time=_optional_float(legacy_result.get("response_time")),
            rag_warnings=warnings,
            reasoning=_optional_text(legacy_result.get("reasoning")),
            compatibility_payload=dict(legacy_result),
        )


def build_legacy_compat_pipeline(
    *,
    legacy_ask: LegacyAsk,
    legacy_stream: LegacyStream,
    pipeline_version_key: str,
) -> EnterpriseRagPipeline:
    """构建 feature flag 使用的过渡管道；后续阶段实现不会改变 route 调用方式。"""
    adapter = LegacyRagAdapter(
        legacy_ask=legacy_ask,
        legacy_stream=legacy_stream,
        pipeline_version_key=pipeline_version_key,
    )
    return EnterpriseRagPipeline(adapter.execute, adapter.stream)


def _evidence_reference_from_legacy(source: Mapping[str, Any], index: int) -> EvidenceReference:
    document_id = str(source.get("document_id") or source.get("doc_id") or source.get("id") or f"legacy-{index}")
    return EvidenceReference(
        citation_id=f"C{index}",
        document_id=document_id,
        title=str(source.get("title") or "未命名来源"),
        source=_optional_text(source.get("source")),
        start_line=_optional_int(source.get("start_line")),
        end_line=_optional_int(source.get("end_line")),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "EnterpriseRagPipeline",
    "LegacyRagAdapter",
    "build_legacy_compat_pipeline",
    "build_pipeline_version_key",
    "query_fingerprint",
]