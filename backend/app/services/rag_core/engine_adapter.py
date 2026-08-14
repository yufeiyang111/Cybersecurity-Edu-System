# -*- coding: utf-8 -*-
"""EnhancedRAGEngine 到公共 RAG Core 的薄适配器。"""
from __future__ import annotations

from typing import Any

from app.config import Config, rag_pipeline_config_snapshot
from app.services.rag_core.evidence_pack_builder import EvidencePackBuilder
from app.services.rag_core.pipeline import EnterpriseRagPipeline, build_pipeline_version_key
from app.services.rag_core.public_rag_executor import ProviderGeneration, PublicRagExecutor
from app.services.rag_core.rerank_stage import RerankStage


def build_public_rag_pipeline(engine: Any) -> EnterpriseRagPipeline:
    """以既有引擎的 Provider/向量适配器构建公共 RAG v2 管道。"""
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
    pipeline_version_key = build_pipeline_version_key(
        config=rag_pipeline_config_snapshot(),
        prompt_version="citation-json-v1",
        embedding_version=embedding_version,
        reranker_version=reranker_version,
    )
    executor = PublicRagExecutor(
        backend=engine.vector_store.backend,
        embedding_service=engine.vector_store.embedding_service,
        generate=lambda messages, request: generate_citation_response(
            engine,
            messages,
            request,
        ),
        pipeline_version_key=pipeline_version_key,
        rerank_stage=RerankStage(),
        evidence_builder=EvidencePackBuilder(),
        strict_citations=Config.RAG_STRICT_CITATIONS,
        candidate_top_k=Config.RAG_CANDIDATE_TOP_K,
        rerank_top_k=Config.RAG_RERANK_TOP_K,
        evidence_token_budget=Config.RAG_EVIDENCE_TOKEN_BUDGET,
    )
    return EnterpriseRagPipeline(executor.execute)


def generate_citation_response(
    engine: Any,
    messages: list[dict[str, str]],
    request,
) -> ProviderGeneration:
    """复用既有 Provider 选择、限额和原始 reasoning 返回，失败只交给执行器降级。"""
    result = engine.generate(
        query="",
        context="",
        user_preferences=dict(request.user_preferences) if request.user_preferences else None,
        user_id=request.user_id,
        operation="qa",
        messages=messages,
    )
    if result.get("warning_code"):
        raise RuntimeError("citation_provider_unavailable")
    raw_response = result.get("answer")
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise RuntimeError("citation_provider_invalid_response")
    return ProviderGeneration(
        raw_response=raw_response,
        reasoning=result.get("reasoning"),
        confidence=result.get("confidence"),
        model_name=result.get("model_name"),
        provider=result.get("provider"),
        model_version=result.get("model_version"),
        response_time=result.get("response_time"),
    )


__all__ = ["build_public_rag_pipeline", "generate_citation_response"]