# -*- coding: utf-8 -*-
"""公共知识库 RAG v2 执行器在离线 mock 下的阶段编排与审计测试。

复用 test_public_rag_executor 的 mock 范式，并锚定到 v1 评测集的真实 gold
evidence（kb-3 等），验证：Candidate→Rerank→Evidence→Citation→Answer 正常链路、
无证据不调 Provider、检索故障降级、严格模式拒绝伪造 citation、Trace 不泄漏。
ungrounded 按设计暂不实装，仅留占位（skip）。
"""
from __future__ import annotations

import json
import re

import pytest

from app.services.rag_core.contracts import RagExecutionRequest
from app.services.vector_stores.contracts import VectorHit
from app.services.rag_core.datasets import EVALUATION_CASES
from app.services.rag_core.evidence_pack_builder import EvidencePackBuilder
from app.services.rag_core.metrics import RagRuntimeMetrics
from app.services.rag_core.public_rag_executor import (
    ProviderGeneration,
    PublicRagExecutor,
)
from app.services.rag_core.rerank_stage import RerankStage


class _EmbeddingService:
    is_degraded = False

    def encode_query(self, query):
        return [[0.1, 0.2]]


class _FixedTokenCounter:
    def count_tokens_with_mode(self, text):
        return 5, "tokenizer"


class _ScoredReranker:
    def __init__(self):
        self.calls = 0

    def rerank(self, query, documents, top_k):
        self.calls += 1
        return [{"id": "0", "rerank_score": 0.9}]


def _case(case_key):
    for case in EVALUATION_CASES:
        if case.case_key == case_key:
            return case
    raise AssertionError(f"missing dataset case {case_key}")


def _backend_returning(doc_id, title, start_line, end_line, corpus_version, text):
    class _Backend:
        def hybrid_search(self, **kwargs):
            return [
                VectorHit(
                    id=f"doc_{doc_id}_chunk_0",
                    text=text,
                    metadata={
                        "doc_id": doc_id,
                        "title": title,
                        "source": "公开知识库",
                        "start_line": start_line,
                        "end_line": end_line,
                        "parent_text": text,
                        "corpus_version": corpus_version,
                        "title_path": "Web安全",
                    },
                    similarity=0.8,
                    distance=0.2,
                    retrieval_metadata={
                        "retrieval_path": "both",
                        "dense_rank": 1,
                        "dense_score": 0.8,
                        "bm25_rank": 1,
                        "bm25_score": 2.1,
                        "rrf_score": 0.03,
                    },
                )
            ]

    return _Backend()


def _executor(*, backend, generation, reranker=None, metrics=None) -> PublicRagExecutor:
    return PublicRagExecutor(
        backend=backend,
        embedding_service=_EmbeddingService(),
        generate=generation,
        pipeline_version_key="rag-v2-public-test",
        rerank_stage=RerankStage(reranker=reranker or _ScoredReranker()),
        evidence_builder=EvidencePackBuilder(token_counter=_FixedTokenCounter(), max_references=2),
        strict_citations=True,
        candidate_top_k=5,
        rerank_top_k=2,
        evidence_token_budget=200,
        metrics=metrics,
    )


def _supported_generation(template: str):
    def generate(messages, request):
        evidence = messages[1]["content"]
        citation_id = re.search(r'citation_id="(C-[a-f0-9]+)"', evidence).group(1)
        return ProviderGeneration(
            raw_response=json.dumps(
                {
                    "answer_status": "supported",
                    "answer": template,
                    "claims": [
                        {
                            "text": "该主张可由当前证据支撑。",
                            "citation_ids": [citation_id],
                        }
                    ],
                    "uncertainty": [],
                },
                ensure_ascii=False,
            ),
            reasoning="仅当前 QA 记录可见的 provider 原始 CoT",
            model_name="test-model",
            provider="test-provider",
            model_version="test-model-v1",
            response_time=0.12,
        )

    return generate


def test_supported_case_runs_pipeline_with_real_evidence_and_no_trace_leak():
    case = _case("v2rag-005")
    ev = case.expected_evidence[0]
    backend = _backend_returning(
        doc_id=ev["document_id"],
        title=ev["title"],
        start_line=ev["start_line"],
        end_line=ev["end_line"],
        corpus_version=ev["corpus_version"],
        text="参数化查询可将数据与 SQL 指令分离，是防御 SQL 注入的首选方案。",
    )

    result = _executor(
        backend=backend,
        generation=_supported_generation("应使用参数化查询处理不可信输入。"),
    ).execute(RagExecutionRequest(query=case.query, request_id="req-v2rag-005"))

    assert result.answer_status == "supported"
    assert len(result.citations.references) == 1
    ref = result.citations.references[0]
    assert ref.document_id == ev["document_id"]
    assert ref.title == ev["title"]
    assert ref.start_line == ev["start_line"]
    assert ref.end_line == ev["end_line"]

    trace = json.dumps(result.trace.to_storage_dict(), ensure_ascii=False)
    assert case.query not in trace
    assert "参数化查询可将数据与 SQL 指令分离" not in trace
    assert "provider 原始 CoT" not in trace


def test_no_evidence_does_not_call_provider():
    class EmptyBackend:
        def hybrid_search(self, **kwargs):
            return []

    called = False

    def generate(messages, request):
        nonlocal called
        called = True
        raise AssertionError("证据为空时不能调用 Provider 生成臆测答案")

    case = _case("v2rag-041")
    result = _executor(backend=EmptyBackend(), generation=generate).execute(
        RagExecutionRequest(query=case.query, request_id="req-empty")
    )

    assert called is False
    assert result.answer_status == "insufficient_evidence"
    assert result.citations.references == ()
    assert "INSUFFICIENT_EVIDENCE" in result.rag_warnings
    assert case.query not in json.dumps(result.trace.to_storage_dict(), ensure_ascii=False)


def test_retrieval_failure_degrades_without_provider():
    class BrokenBackend:
        def hybrid_search(self, **kwargs):
            raise RuntimeError("qdrant endpoint must not reach the user")

    result = _executor(
        backend=BrokenBackend(),
        generation=lambda messages, request: (_ for _ in ()).throw(
            AssertionError("检索故障时不得调用 Provider")
        ),
    ).execute(RagExecutionRequest(query="检索故障", request_id="req-broken"))

    assert result.answer_status == "degraded"
    assert "QDRANT_UNAVAILABLE" in result.rag_warnings
    assert result.citations.references == ()
    assert "qdrant endpoint" not in json.dumps(result.trace.to_storage_dict(), ensure_ascii=False)


def test_strict_mode_rejects_forged_citation():
    def generate(messages, request):
        return ProviderGeneration(
            raw_response=json.dumps(
                {
                    "answer_status": "supported",
                    "answer": "不能验证的回答",
                    "claims": [{"text": "伪造主张", "citation_ids": ["C-forged"]}],
                    "uncertainty": [],
                },
                ensure_ascii=False,
            ),
        )

    case = _case("v2rag-005")
    ev = case.expected_evidence[0]
    backend = _backend_returning(
        doc_id=ev["document_id"],
        title=ev["title"],
        start_line=ev["start_line"],
        end_line=ev["end_line"],
        corpus_version=ev["corpus_version"],
        text="参数化查询可将数据与 SQL 指令分离，是防御 SQL 注入的首选方案。",
    )
    result = _executor(backend=backend, generation=generate).execute(
        RagExecutionRequest(query="测试伪造引用", request_id="req-forged")
    )

    assert result.answer_status == "degraded"
    assert "CITATION_VALIDATION_FAILED" in result.rag_warnings
    assert "STRICT_CITATION_REJECTED" in result.rag_warnings
    assert result.citations.claim_citations == {}


def test_ungrounded_branch_enters_only_after_insufficient_evidence():
    class EmptyBackend:
        def hybrid_search(self, **kwargs):
            return []

    generation_calls = []

    def generate(messages, request):
        generation_calls.append(messages)
        return ProviderGeneration(
            raw_response="基于通用网络安全知识，SQL 注入可通过参数化查询等手段缓解。",
            model_name="test-model",
            provider="test-provider",
            model_version="test-model-v1",
            response_time=0.1,
        )

    case = _case("v2rag-041")
    result = _executor(
        backend=EmptyBackend(),
        generation=generate,
    ).execute(
        RagExecutionRequest(
            query=case.query,
            request_id="req-ungrounded",
            allow_ungrounded_answers=True,
        )
    )

    # 仅在 insufficient_evidence 之后才进入 ungrounded 分支。
    assert result.answer_status == "ungrounded"
    # citations 必须为空，不得伪造来源/行号/证据。
    assert result.citations.references == ()
    assert "C-" not in result.answer
    # 必须包含规定的可审计 warning（spec 要求码 + 既有兼容码）。
    assert "NO_RETRIEVED_EVIDENCE" in result.rag_warnings
    assert "USER_APPROVED_UNGROUNDED_ANSWER" in result.rag_warnings
    assert "USER_PREFERENCE_UNGROUNDED_ANSWER" in result.rag_warnings
    # 前端展示用的「未检索到可验证内容」警示必须随答案返回。
    assert "未检索到任何可验证" in result.answer
    assert generation_calls  # 确实走了无证据通用回答生成分支
    assert case.query not in json.dumps(result.trace.to_storage_dict(), ensure_ascii=False)


def test_ungrounded_not_entered_when_retrieval_fails():
    class BrokenBackend:
        def hybrid_search(self, **kwargs):
            raise RuntimeError("qdrant endpoint down")

    result = _executor(
        backend=BrokenBackend(),
        generation=lambda messages, request: (_ for _ in ()).throw(
            AssertionError("ungrounded 不得绕过检索故障")
        ),
    ).execute(
        RagExecutionRequest(
            query="检索故障",
            request_id="req-ungrounded-broken",
            allow_ungrounded_answers=True,
        )
    )

    # 检索故障必须降级，不得误入 ungrounded（避免绕过故障直接编造）。
    assert result.answer_status == "degraded"
    assert "QDRANT_UNAVAILABLE" in result.rag_warnings
    assert result.answer_status != "ungrounded"
