# -*- coding: utf-8 -*-
"""离线指标与发布门禁集成测试（dataset-driven，全 mock，无真实基础设施）。

验证 hit@1/3/5、MRR、按 category 与 difficulty 分组、insufficient 正确率、
unsafe citation 计数，以及 Release Gate 在脱敏前提下可运行且 corpus_version 一致。
真实 Qdrant / embedding / reranker / Provider 效果不在此断言。
"""
from __future__ import annotations

import json

import pytest

from app.services.rag_core.contracts import CitationManifest, EvidenceReference
from app.services.rag_core.datasets import CORPUS_VERSION, EVALUATION_CASES
from app.services.rag_core.evaluation_contracts import (
    EvaluationCase,
    EvaluationExecution,
)
from app.services.rag_core.evaluator import OfflineRagEvaluator
from app.services.rag_core.release_gate import ReleaseGateVerifier

CORPUS = CORPUS_VERSION
PIPELINE_KEY = "rag-v2-public-test"
FINGERPRINT = "config-test"


def _references_for(case: EvaluationCase):
    refs = []
    claim_citations: dict[str, tuple[str, ...]] = {}
    for index, ev in enumerate(case.expected_evidence, start=1):
        citation_id = f"C-{index}"
        refs.append(
            EvidenceReference(
                citation_id=citation_id,
                document_id=ev["document_id"],
                title=ev["title"],
                source="public",
                start_line=ev["start_line"],
                end_line=ev["end_line"],
                chunk_id=ev["chunk_id"],
                corpus_version=ev["corpus_version"],
            )
        )
        claim_citations[f"claim-{index}"] = (citation_id,)
    return refs, claim_citations


def _execution_for(case: EvaluationCase) -> EvaluationExecution:
    if case.category == "retrieval_supported":
        refs, claim_citations = _references_for(case)
        return EvaluationExecution(
            candidate_document_ids=tuple(case.expected_document_ids),
            evidence_references=tuple(refs),
            citation_manifest=CitationManifest(references=tuple(refs), claim_citations=claim_citations),
            answer_status="supported",
            status_observable=True,
            citation_observable=True,
            pipeline_version_key=PIPELINE_KEY,
            corpus_version=CORPUS,
            config_fingerprint=FINGERPRINT,
            retrieval_ms=12,
            rerank_ms=4,
        )
    return EvaluationExecution(
        candidate_document_ids=(),
        evidence_references=(),
        citation_manifest=CitationManifest(references=(), claim_citations={}),
        answer_status="insufficient_evidence",
        status_observable=True,
        citation_observable=True,
        pipeline_version_key=PIPELINE_KEY,
        corpus_version=CORPUS,
        config_fingerprint=FINGERPRINT,
        retrieval_ms=8,
        rerank_ms=0,
    )


def _run(pipeline: str):
    return OfflineRagEvaluator(execute_case=_execution_for).evaluate(
        tuple(EVALUATION_CASES), pipeline=pipeline, corpus_version=CORPUS
    )


def test_offline_evaluation_produces_required_metrics():
    report = _run("v2")
    payload = report.to_report_dict()
    retrieval = payload["metrics"]["retrieval"]
    assert retrieval["recall_at_1"] is not None
    assert retrieval["recall_at_3"] is not None
    assert retrieval["recall_at_5"] is not None
    assert retrieval["mrr"] is not None
    assert retrieval["ndcg_at_10"] is not None

    citation = payload["metrics"]["citation"]
    # status_matches_expected 是布尔指标，不参与均值（_finite_number 过滤 bool），
    # 故在单 outcome 维度校验：所有 case 的实际状态都与期望一致。
    assert all(o.citation_metrics["status_matches_expected"] is True for o in report.outcomes)
    assert citation.get("unsafe_supported_negative_count", 0) == 0

    assert report.release_blockers == ()
    assert report.metrics["failure_stages"] == {}


def test_metrics_are_grouped_by_category_and_difficulty():
    report = _run("v2")
    payload = report.to_report_dict()

    for category in {"retrieval_supported", "insufficient_evidence", "adversarial_or_boundary"}:
        assert category in payload["by_category"]
        assert payload["by_category"][category]["case_count"] > 0

    total = sum(g["case_count"] for g in payload["by_category"].values())
    assert total == report.case_count == len(EVALUATION_CASES)

    for difficulty in {"easy", "medium", "hard"}:
        assert difficulty in payload["by_difficulty"]
        assert payload["by_difficulty"][difficulty]["case_count"] > 0


def test_report_excludes_query_body_and_prompt():
    report = _run("v2")
    serialized = json.dumps(report.to_report_dict(), ensure_ascii=False)
    for case in EVALUATION_CASES:
        assert case.query not in serialized
    assert "参数化查询可将数据与 SQL 指令分离" not in serialized


def test_release_gate_runs_on_v2_and_legacy_without_leak():
    v2 = _run("v2").to_report_dict()
    legacy = _run("legacy").to_report_dict()

    result = ReleaseGateVerifier().verify(legacy_report=legacy, v2_report=v2)
    payload = result.to_dict(epsilon=1e-9)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "CORPUS_VERSION_MISMATCH" not in result.blockers
    # 门禁输出不得泄漏任何评测集 query 或知识库正文。
    for case in EVALUATION_CASES:
        assert case.query not in serialized
    assert "参数化查询可将数据与 SQL 指令分离" not in serialized
