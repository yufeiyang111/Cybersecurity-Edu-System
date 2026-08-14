# -*- coding: utf-8 -*-
"""RAG 离线评测 CLI 的显式模式与脱敏输出测试。"""
from __future__ import annotations

import json

import pytest

from app.services.rag_core.contracts import CitationManifest, EvidenceReference
from app.services.rag_core.evaluator import (
    EvaluationCase,
    EvaluationExecution,
)


def _case(case_id: int) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        case_key=f"case-{case_id}",
        category="concept",
        difficulty="medium",
        expected_document_ids=("doc-a",),
        expected_status="supported",
        review_note="人工审核：CLI 测试标签",
        query="raw query must not appear in report",
    )


def _execution() -> EvaluationExecution:
    reference = EvidenceReference(
        citation_id="C1",
        document_id="doc-a",
        title="private evidence title",
        source="public",
        start_line=1,
        end_line=2,
    )
    return EvaluationExecution(
        candidate_document_ids=("doc-a",),
        evidence_references=(reference,),
        citation_manifest=CitationManifest(
            references=(reference,),
            claim_citations={"claim": ("C1",)},
        ),
        answer_status="supported",
        status_observable=True,
        citation_observable=True,
        pipeline_version_key="rag-v2-cli-test",
        corpus_version="public-knowledge-20260814",
        config_fingerprint="config-cli-test",
        retrieval_ms=5,
        rerank_ms=2,
        evidence_token_count=100,
        evidence_token_budget=500,
    )


def test_cli_parser_requires_explicit_pipeline_and_corpus_version():
    from app.scripts.rag_evaluate import build_argument_parser

    parser = build_argument_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = parser.parse_args(
        ["--pipeline", "v2", "--corpus-version", "public-knowledge-20260814"]
    )
    assert args.pipeline == "v2"
    assert args.corpus_version == "public-knowledge-20260814"


def test_enterprise_run_writes_and_persists_only_safe_summary(monkeypatch):
    from app.scripts import rag_evaluate

    monkeypatch.setattr(rag_evaluate, "write_report", lambda report, name: name)
    monkeypatch.setattr(rag_evaluate, "persist_evaluation_report", lambda report, report_path: 73)

    payload = rag_evaluate.run_enterprise_evaluation(
        pipeline="v2",
        corpus_version="public-knowledge-20260814",
        cases=(_case(1),),
        executor=lambda case: _execution(),
        report_name="rag_report_test_v2.json",
        persist=True,
    )
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["run_id"] == 73
    assert payload["report_file"] == "rag_report_test_v2.json"
    assert payload["case_count"] == 1
    assert "raw query" not in serialized
    assert "private evidence title" not in serialized


def test_enterprise_run_rejects_empty_active_case_set_before_calling_provider():
    from app.scripts.rag_evaluate import run_enterprise_evaluation

    with pytest.raises(ValueError, match="评测集为空"):
        run_enterprise_evaluation(
            pipeline="legacy",
            corpus_version="public-knowledge-20260814",
            cases=(),
            executor=lambda case: (_ for _ in ()).throw(AssertionError("must not run")),
            persist=False,
        )
