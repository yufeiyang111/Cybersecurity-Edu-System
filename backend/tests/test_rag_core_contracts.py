# -*- coding: utf-8 -*-
"""Enterprise RAG Core 契约、配置和 legacy 灰度兼容测试。"""
from __future__ import annotations

import json

import pytest

from app.config import (
    Config,
    rag_runtime_config_snapshot,
    resolve_rag_pipeline_settings,
)
from app.services.rag_core import (
    CitationManifest,
    EnterpriseRagPipeline,
    EvidenceReference,
    RagExecutionRequest,
    RagExecutionResult,
    RetrievalTrace,
    build_legacy_compat_pipeline,
    build_pipeline_version_key,
)


def _trace() -> RetrievalTrace:
    return RetrievalTrace(
        request_id="request-1",
        query_fingerprint="f" * 64,
        pipeline_version_key="rag-v2-test",
        stage_summary={"candidate_count": 3},
        warnings=("RERANKER_DEGRADED",),
        retrieval_ms=12,
    )


def _result() -> RagExecutionResult:
    reference = EvidenceReference(
        citation_id="C1",
        document_id="42",
        title="SQL 注入基础",
        source="HackTricks",
        start_line=10,
        end_line=20,
        content="仅在内存中用于生成答案的证据正文",
    )
    return RagExecutionResult(
        answer="答案 [C1]",
        answer_status="supported",
        citations=CitationManifest(
            references=(reference,),
            claim_citations={"答案": ("C1",)},
        ),
        trace=_trace(),
        reasoning="provider 原始推理仅允许当前记录展示",
    )


def test_rag_pipeline_settings_defaults_are_safe_and_disabled():
    settings = resolve_rag_pipeline_settings({})

    assert settings == {
        "pipeline_v2_enabled": False,
        "candidate_top_k": 40,
        "rerank_top_k": 15,
        "evidence_top_k": 6,
        "evidence_token_budget": 3500,
        "diagnostics_enabled": False,
        "strict_citations": False,
        "metrics_sample_limit": 512,
    }
    assert Config.RAG_PIPELINE_V2_ENABLED is False


@pytest.mark.parametrize(
    "values, message",
    [
        ({"RAG_CANDIDATE_TOP_K": "9"}, "RAG_CANDIDATE_TOP_K"),
        ({"RAG_RERANK_TOP_K": "31"}, "RAG_RERANK_TOP_K"),
        ({"RAG_EVIDENCE_TOP_K": "11"}, "RAG_EVIDENCE_TOP_K"),
        ({"RAG_EVIDENCE_TOKEN_BUDGET": "499"}, "RAG_EVIDENCE_TOKEN_BUDGET"),
        ({"RAG_METRICS_SAMPLE_LIMIT": "15"}, "RAG_METRICS_SAMPLE_LIMIT"),
        ({"RAG_METRICS_SAMPLE_LIMIT": "5001"}, "RAG_METRICS_SAMPLE_LIMIT"),
        ({"RAG_PIPELINE_V2_ENABLED": "maybe"}, "RAG_PIPELINE_V2_ENABLED"),
        (
            {"RAG_CANDIDATE_TOP_K": "10", "RAG_RERANK_TOP_K": "15"},
            "RAG_RERANK_TOP_K",
        ),
        (
            {"RAG_RERANK_TOP_K": "3", "RAG_EVIDENCE_TOP_K": "6"},
            "RAG_EVIDENCE_TOP_K",
        ),
    ],
)
def test_rag_pipeline_settings_reject_invalid_values(values, message):
    with pytest.raises(ValueError, match=message):
        resolve_rag_pipeline_settings(values)


def test_pipeline_version_key_is_stable_and_changes_for_config_or_model():
    config = {
        "candidate_top_k": 40,
        "rerank_top_k": 15,
        "evidence_top_k": 6,
        "evidence_token_budget": 3500,
        "pipeline_v2_enabled": False,
    }
    first = build_pipeline_version_key(
        config=config,
        prompt_version="prompt-v1",
        embedding_version="bge-m3",
        reranker_version="reranker-v2",
    )
    second = build_pipeline_version_key(
        config=dict(reversed(list(config.items()))),
        prompt_version="prompt-v1",
        embedding_version="bge-m3",
        reranker_version="reranker-v2",
    )
    changed_config = build_pipeline_version_key(
        config={**config, "candidate_top_k": 50},
        prompt_version="prompt-v1",
        embedding_version="bge-m3",
        reranker_version="reranker-v2",
    )
    changed_model = build_pipeline_version_key(
        config=config,
        prompt_version="prompt-v1",
        embedding_version="bge-m3-next",
        reranker_version="reranker-v2",
    )

    assert first == second
    assert first.startswith("rag-v2-")
    assert first != changed_config
    assert first != changed_model


def test_trace_and_citation_manifest_exclude_content_and_reasoning():
    result = _result()
    trace_payload = json.dumps(result.trace.to_storage_dict(), ensure_ascii=False)
    manifest_payload = json.dumps(result.citations.to_dict(), ensure_ascii=False)

    assert "证据正文" not in trace_payload
    assert "provider 原始推理" not in trace_payload
    assert "证据正文" not in manifest_payload
    assert "provider 原始推理" not in manifest_payload
    assert result.to_legacy_payload()["reasoning"] == "provider 原始推理仅允许当前记录展示"


def test_pipeline_accepts_fake_executor_and_rejects_invalid_result():
    expected = _result()
    request = RagExecutionRequest(query="什么是 SQL 注入？")
    pipeline = EnterpriseRagPipeline(lambda received: expected)

    assert pipeline.execute(request) is expected
    assert list(pipeline.stream(request))[0]["answer"] == "答案 [C1]"

    invalid_pipeline = EnterpriseRagPipeline(lambda received: {"answer": "not-a-contract"})
    with pytest.raises(TypeError, match="RagExecutionResult"):
        invalid_pipeline.execute(request)


def test_legacy_adapter_preserves_existing_payload_and_adds_v2_metadata():
    legacy_payload = {
        "answer": "旧链路回答",
        "reasoning": "provider 原始 CoT",
        "sources": [
            {
                "title": "SQL 注入基础",
                "source": "HackTricks",
                "similarity": 0.73,
                "doc_id": "42",
                "start_line": 10,
                "end_line": 20,
            }
        ],
        "retrieved_docs": [{"id": "42", "similarity": 0.73}],
        "confidence": 0.73,
        "warning_code": None,
        "rag_warnings": ["RERANKER_DEGRADED"],
    }
    pipeline = build_legacy_compat_pipeline(
        legacy_ask=lambda **kwargs: legacy_payload,
        legacy_stream=lambda **kwargs: iter(({"type": "done", **legacy_payload},)),
        pipeline_version_key="rag-v2-compat",
    )
    request = RagExecutionRequest(query="SQL 注入如何防护？", request_id="req-2")

    result = pipeline.execute(request).to_legacy_payload()
    events = list(pipeline.stream(request))

    assert result["sources"][0]["similarity"] == 0.73
    assert result["retrieved_docs"] == legacy_payload["retrieved_docs"]
    assert result["reasoning"] == "provider 原始 CoT"
    assert result["answer_status"] == "degraded"
    assert result["citations"]["citations"][0]["document_id"] == "42"
    assert events[-1]["sources"][0]["similarity"] == 0.73
    assert events[-1]["pipeline_version"] == "rag-v2-compat"


def test_enhanced_engine_flag_defaults_to_legacy_and_v2_uses_rag_core_contract(monkeypatch):
    from app.services.enhanced_rag_engine import EnhancedRAGEngine

    legacy_payload = {
        "answer": "兼容回答",
        "reasoning": "可展示的 provider 原始 CoT",
        "sources": [{"title": "来源", "doc_id": "doc-1", "similarity": 0.62}],
        "retrieved_docs": [{"id": "doc-1", "similarity": 0.62}],
        "confidence": 0.62,
        "rag_warnings": [],
    }
    engine = object.__new__(EnhancedRAGEngine)
    engine._ask_legacy = lambda *args, **kwargs: dict(legacy_payload)
    engine._ask_stream_legacy = lambda *args, **kwargs: iter(({"type": "done", **legacy_payload},))

    monkeypatch.setattr(Config, "RAG_PIPELINE_V2_ENABLED", False)
    assert engine.ask("测试问题") == legacy_payload

    v2_result = _result()
    pipeline = EnterpriseRagPipeline(lambda request: v2_result)
    engine._enterprise_rag_pipeline = lambda: pipeline
    monkeypatch.setattr(Config, "RAG_PIPELINE_V2_ENABLED", True)
    result = engine.ask("测试问题")
    stream_result = list(engine.ask_stream("测试问题"))[-1]

    assert result["answer"] == "答案 [C1]"
    assert result["citations"]["citations"][0]["citation_id"] == "C1"
    assert result["reasoning"] == "provider 原始推理仅允许当前记录展示"
    assert result["pipeline_version"] == "rag-v2-test"
    assert stream_result["citations"]["citations"][0]["document_id"] == "42"


def test_rag_runtime_config_snapshot_exposes_only_effective_non_sensitive_flags(monkeypatch):
    monkeypatch.setattr(Config, "RAG_PIPELINE_V2_ENABLED", False)
    monkeypatch.setattr(Config, "RAG_STRICT_CITATIONS", True)
    monkeypatch.setattr(Config, "RAG_DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(Config, "RAG_METRICS_SAMPLE_LIMIT", 16)

    snapshot = rag_runtime_config_snapshot()

    assert snapshot == {
        "pipeline_mode": "legacy",
        "pipeline_v2_enabled": False,
        "strict_citations_enabled": False,
        "diagnostics_enabled": True,
        "metrics_sample_limit": 16,
    }
