# -*- coding: utf-8 -*-
"""公共知识库 RAG Core 的唯一执行器：Candidate→Rerank→Evidence→Citation→Answer。"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from time import perf_counter

from app.services.rag_core.answer_composer import AnswerComposer
from app.services.rag_core.public_rag_result_factory import (
    ProviderGeneration,
    composed_result,
    generation_warnings,
    rerank_warnings,
    terminal_result,
    ungrounded_result,
    unique_warnings,
)
from app.services.rag_core.candidate_retriever import CandidateRetriever
from app.services.rag_core.citation_manifest import CitationManifestBuilder
from app.services.rag_core.contracts import (
    CitationManifest,
    RagExecutionRequest,
    RagExecutionResult,
)
from app.services.rag_core.evidence_pack_builder import EvidencePackBuilder
from app.services.rag_core.execution_observer import record_execution_result
from app.services.rag_core.metrics import RagRuntimeMetrics
from app.services.rag_core.rerank_stage import RerankResult, RerankStage


GenerationPort = Callable[[list[dict[str, str]], RagExecutionRequest], ProviderGeneration]


class PublicRagExecutor:
    """深模块：调用方只传请求，内部封装公共 RAG 的完整阶段和安全降级。"""

    def __init__(
        self,
        *,
        backend,
        embedding_service,
        generate: GenerationPort | None,
        pipeline_version_key: str,
        rerank_stage: RerankStage,
        evidence_builder: EvidencePackBuilder,
        strict_citations: bool,
        candidate_top_k: int,
        rerank_top_k: int,
        evidence_token_budget: int,
        candidate_retriever: CandidateRetriever | None = None,
        citation_manifest_builder: CitationManifestBuilder | None = None,
        answer_composer: AnswerComposer | None = None,
        metrics: RagRuntimeMetrics | None = None,
    ) -> None:
        if not pipeline_version_key or not pipeline_version_key.strip():
            raise ValueError("pipeline_version_key is required")
        if candidate_top_k <= 0 or rerank_top_k <= 0 or evidence_token_budget <= 0:
            raise ValueError("RAG stage limits must be positive")
        if rerank_top_k > candidate_top_k:
            raise ValueError("rerank_top_k cannot exceed candidate_top_k")
        self._embedding_service = embedding_service
        self._generate = generate
        self._pipeline_version_key = pipeline_version_key.strip()[:64]
        self._candidate_top_k = candidate_top_k
        self._rerank_top_k = rerank_top_k
        self._evidence_token_budget = evidence_token_budget
        self._strict_citations = strict_citations
        self._candidate_retriever = candidate_retriever or CandidateRetriever(backend)
        self._rerank_stage = rerank_stage
        self._evidence_builder = evidence_builder
        self._citation_manifest_builder = citation_manifest_builder or CitationManifestBuilder()
        self._answer_composer = answer_composer or AnswerComposer()
        self._metrics = metrics

    def execute(self, request: RagExecutionRequest) -> RagExecutionResult:
        """执行公共 RAG 全链路；所有降级明确标注，禁止无证据调用模型。"""
        started_at = perf_counter()
        candidate_started_at = perf_counter()
        query_vector, embedding_degraded, embedding_warnings = self._query_vector(request.query)
        candidate_result = self._candidate_retriever.retrieve(
            request.query,
            vector=query_vector,
            top_k=self._candidate_top_k,
            embedding_degraded=embedding_degraded,
        )
        candidate_elapsed_ms = _elapsed_ms(candidate_started_at)

        rerank_result = self._rerank(request, candidate_result.candidates)

        evidence_started_at = perf_counter()
        evidence_result = self._evidence_builder.build(
            rerank_result.candidates,
            token_budget=self._evidence_token_budget,
        )
        evidence_elapsed_ms = _elapsed_ms(evidence_started_at)
        retrieval_ms = _elapsed_ms(started_at)
        warnings = unique_warnings(
            embedding_warnings,
            candidate_result.warnings,
            rerank_warnings(rerank_result),
            evidence_result.warnings,
        )
        trace_stages = {
            "candidate": {
                **candidate_result.trace_summary(),
                "elapsed_ms": candidate_elapsed_ms,
                "candidates": [
                    candidate.trace_summary()
                    for candidate in candidate_result.candidates
                ],
            },
            "rerank": rerank_result.trace_summary(),
            "evidence": {
                **evidence_result.trace_summary(),
                "elapsed_ms": evidence_elapsed_ms,
            },
        }

        if "QDRANT_UNAVAILABLE" in warnings:
            return self._record_result(terminal_result(
                request=request,
                pipeline_version_key=self._pipeline_version_key,
                answer="检索服务暂时不可用，当前无法提供可验证的知识库回答。",
                answer_status="degraded",
                citations=CitationManifest(references=()),
                warnings=warnings,
                trace_stages=trace_stages,
                retrieval_ms=retrieval_ms,
            ))
        if evidence_result.answer_status == "insufficient_evidence":
            if request.allow_ungrounded_answers:
                return self._generate_ungrounded_answer(
                    request=request,
                    warnings=warnings,
                    trace_stages=trace_stages,
                    retrieval_ms=retrieval_ms,
                )
            return self._record_result(terminal_result(
                request=request,
                pipeline_version_key=self._pipeline_version_key,
                answer="当前知识库没有找到足够的可定位证据，暂时无法提供可验证的回答。",
                answer_status="insufficient_evidence",
                citations=CitationManifest(references=()),
                warnings=warnings,
                trace_stages=trace_stages,
                retrieval_ms=retrieval_ms,
            ))
        citation_manifest = self._citation_manifest_builder.build(evidence_result.pack)
        from app.services.rag_citation_prompt import build_citation_qa_messages

        messages = build_citation_qa_messages(request.query, citation_manifest)
        generation_started_at = perf_counter()
        generation = self._generate_answer(messages, request)
        generation_elapsed_ms = _elapsed_ms(generation_started_at)
        trace_stages["generation"] = {
            "status": "completed" if generation is not None else "failed",
            "elapsed_ms": generation_elapsed_ms,
        }
        if generation is None:
            return self._record_result(terminal_result(
                request=request,
                pipeline_version_key=self._pipeline_version_key,
                answer="生成服务暂时不可用，当前无法提供可验证的回答。",
                answer_status="degraded",
                citations=CitationManifest(references=citation_manifest.references),
                warnings=unique_warnings(warnings, ("LLM_PROVIDER_REQUEST_FAILED",)),
                trace_stages=trace_stages,
                retrieval_ms=retrieval_ms,
            ))

        try:
            composition = self._answer_composer.compose(
                generation.raw_response,
                citation_manifest=citation_manifest,
                strict_citations=self._strict_citations,
            )
        except Exception:
            return self._record_result(terminal_result(
                request=request,
                pipeline_version_key=self._pipeline_version_key,
                answer="引用校验服务暂时不可用，当前无法提供可验证的回答。",
                answer_status="degraded",
                citations=CitationManifest(references=citation_manifest.references),
                warnings=unique_warnings(warnings, ("CITATION_VALIDATOR_UNAVAILABLE",)),
                trace_stages=trace_stages,
                retrieval_ms=retrieval_ms,
            ))

        all_warnings = unique_warnings(warnings, composition.warnings, generation_warnings(generation))
        return self._record_result(composed_result(
            request=request,
            pipeline_version_key=self._pipeline_version_key,
            composition=composition,
            generation=generation,
            warnings=all_warnings,
            trace_stages=trace_stages,
            retrieval_ms=retrieval_ms,
        ))

    def _generate_ungrounded_answer(
        self,
        *,
        request: RagExecutionRequest,
        warnings: tuple[str, ...],
        trace_stages: dict,
        retrieval_ms: int,
    ) -> RagExecutionResult:
        """在用户长期偏好已开启时生成明确标识的无证据通用回答。"""
        from app.services.rag_ungrounded_prompt import (
            UNGROUNDED_ANSWER_NOTICE,
            build_ungrounded_qa_messages,
        )

        messages = build_ungrounded_qa_messages(
            request.query,
            conversation_history=request.conversation_history,
            user_preferences=request.user_preferences,
            memories=request.memories,
        )
        generation_started_at = perf_counter()
        generation = self._generate_answer(messages, request)
        trace_stages["ungrounded_generation"] = {
            "status": "completed" if generation is not None else "failed",
            "elapsed_ms": _elapsed_ms(generation_started_at),
        }
        ungrounded_warnings = unique_warnings(
            warnings,
            (
                "NO_RETRIEVED_EVIDENCE",
                "USER_PREFERENCE_UNGROUNDED_ANSWER",
                # spec 要求的审计码别名；与上面并存，便于既有/新审计逻辑兼容。
                "USER_APPROVED_UNGROUNDED_ANSWER",
            ),
        )
        if generation is None:
            return self._record_result(terminal_result(
                request=request,
                pipeline_version_key=self._pipeline_version_key,
                answer="生成服务暂时不可用，当前无法提供基于通用知识的回答。",
                answer_status="degraded",
                citations=CitationManifest(references=()),
                warnings=unique_warnings(
                    ungrounded_warnings,
                    ("LLM_PROVIDER_REQUEST_FAILED",),
                ),
                trace_stages=trace_stages,
                retrieval_ms=retrieval_ms,
            ))
        return self._record_result(ungrounded_result(
            request=request,
            pipeline_version_key=self._pipeline_version_key,
            generation=generation,
            warnings=unique_warnings(
                ungrounded_warnings,
                generation_warnings(generation),
            ),
            trace_stages=trace_stages,
            retrieval_ms=retrieval_ms,
            notice=UNGROUNDED_ANSWER_NOTICE,
        ))

    def _record_result(self, result: RagExecutionResult) -> RagExecutionResult:
        """记录受控运行指标；指标系统异常不得影响回答。"""
        return record_execution_result(self._metrics, result)

    def _query_vector(self, query: str) -> tuple[Sequence[float] | None, bool, tuple[str, ...]]:
        """获取 query 向量；embedding 降级或异常时显式转为词法检索。"""
        if bool(getattr(self._embedding_service, "is_degraded", False)):
            return None, True, ("EMBEDDING_DEGRADED",)
        try:
            encoded = self._embedding_service.encode_query(query)
            if hasattr(encoded, "tolist"):
                encoded = encoded.tolist()
            if not isinstance(encoded, Sequence) or isinstance(encoded, (str, bytes)):
                raise ValueError("invalid embedding vector")
            vector = encoded
            if (
                vector
                and isinstance(vector[0], Sequence)
                and not isinstance(vector[0], (str, bytes))
            ):
                vector = vector[0]
            if not vector or isinstance(vector, (str, bytes)):
                raise ValueError("invalid embedding vector")
            return list(vector), False, ()
        except Exception:
            return None, True, ("EMBEDDING_UNAVAILABLE",)

    def _rerank(self, request: RagExecutionRequest, candidates) -> RerankResult:
        """按请求开关执行重排；关闭时保留 Candidate 的原顺序。"""
        if request.use_rerank:
            return self._rerank_stage.rerank(
                request.query,
                candidates,
                top_k=self._rerank_top_k,
            )
        selected = tuple(candidates[: self._rerank_top_k])
        return RerankResult(
            candidates=selected,
            status="skipped",
            input_count=len(candidates),
            output_count=len(selected),
            elapsed_ms=0,
            failure_type="disabled",
        )

    def _generate_answer(
        self,
        messages: list[dict[str, str]],
        request: RagExecutionRequest,
    ) -> ProviderGeneration | None:
        """隔离 Provider 边界；异常正文不进入结果、日志或 trace。"""
        if self._generate is None:
            return None
        try:
            generation = self._generate(messages, request)
        except Exception:
            return None
        return generation if isinstance(generation, ProviderGeneration) else None

def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


__all__ = ["ProviderGeneration", "PublicRagExecutor"]
