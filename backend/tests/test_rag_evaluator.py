# -*- coding: utf-8 -*-
"""?? RAG ????????????????"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.services.rag_core.contracts import CitationManifest, EvidenceReference
from app.services.rag_core.evaluator import (
    EvaluationCase,
    EvaluationExecution,
    OfflineRagEvaluator,
)


def _reference(citation_id: str, document_id: str) -> EvidenceReference:
    return EvidenceReference(
        citation_id=citation_id,
        document_id=document_id,
        title=f"Title {document_id}",
        source="public",
        start_line=1,
        end_line=3,
    )


def _execution(
    *,
    candidate_document_ids=("doc-a",),
    answer_status="supported",
    status_observable=True,
    citation_observable=True,
    references=(_reference("C1", "doc-a"),),
    claim_citations=None,
) -> EvaluationExecution:
    return EvaluationExecution(
        candidate_document_ids=tuple(candidate_document_ids),
        evidence_references=tuple(references),
        citation_manifest=CitationManifest(
            references=tuple(references),
            claim_citations=claim_citations or {"claim": ("C1",)},
        ),
        answer_status=answer_status,
        status_observable=status_observable,
        citation_observable=citation_observable,
        pipeline_version_key="rag-v2-test",
        corpus_version="public-knowledge-20260814",
        config_fingerprint="config-test",
        retrieval_ms=12,
        rerank_ms=4,
    )


def _case(
    case_id: int,
    *,
    category="concept",
    expected_ids=("doc-a",),
    expected_status="supported",
) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        case_key=f"case-{case_id}",
        category=category,
        difficulty="medium",
        expected_document_ids=tuple(expected_ids),
        expected_status=expected_status,
        review_note="?????????",
    )


def test_v2_report_groups_metrics_and_never_serializes_raw_query_or_evidence_content():
    cases = (
        _case(1),
        _case(
            2,
            category="insufficient",
            expected_ids=(),
            expected_status="insufficient_evidence",
        ),
    )
    evaluator = OfflineRagEvaluator(
        execute_case=lambda case: (
            _execution()
            if case.case_id == 1
            else _execution(
                candidate_document_ids=(),
                answer_status="insufficient_evidence",
                references=(),
                claim_citations={},
            )
        )
    )

    report = evaluator.evaluate(
        cases,
        pipeline="v2",
        corpus_version="public-knowledge-20260814",
    )
    payload = report.to_report_dict()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["pipeline"] == "v2"
    assert payload["case_count"] == 2
    assert payload["metrics"]["retrieval"]["recall_at_20"] == pytest.approx(1.0)
    assert payload["by_category"]["insufficient"]["case_count"] == 1
    assert "query" not in serialized.lower()
    assert "Title doc-a" not in serialized
    assert "case-1" not in serialized


def test_negative_case_supported_status_is_a_release_blocking_violation():
    evaluator = OfflineRagEvaluator(execute_case=lambda case: _execution())

    report = evaluator.evaluate(
        (_case(7, category="injection", expected_ids=(), expected_status="insufficient_evidence"),),
        pipeline="v2",
        corpus_version="public-knowledge-20260814",
    )

    outcome = report.outcomes[0]
    assert outcome.failure_stage == "answer_status"
    assert outcome.citation_metrics["unsafe_supported_negative"] is True
    assert report.release_blockers == ("NEGATIVE_CASE_MARKED_SUPPORTED",)


def test_legacy_execution_does_not_fake_v2_answer_or_citation_observability():
    evaluator = OfflineRagEvaluator(
        execute_case=lambda case: _execution(
            answer_status=None,
            status_observable=False,
            citation_observable=False,
            claim_citations={},
        )
    )

    report = evaluator.evaluate(
        (_case(8),),
        pipeline="legacy",
        corpus_version="public-knowledge-20260814",
    )

    outcome = report.outcomes[0]
    assert outcome.citation_metrics["status_matches_expected"] is None
    assert outcome.citation_metrics["citation_observable"] is False
    assert report.release_blockers == ()


def test_executor_failure_is_classified_without_exposing_exception_or_case_text():
    def explode(_case):
        raise RuntimeError("raw query and provider exception must not leak")

    evaluator = OfflineRagEvaluator(execute_case=explode)
    report = evaluator.evaluate(
        (_case(9, expected_ids=("top-secret-doc",)),),
        pipeline="v2",
        corpus_version="public-knowledge-20260814",
    )

    outcome = report.outcomes[0]
    payload = report.to_report_dict()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert outcome.failure_stage == "execution"
    assert outcome.notes == ("EVALUATION_EXECUTION_FAILED",)
    assert "raw query" not in serialized
    assert "top-secret-doc" not in serialized


def test_evaluator_requires_explicit_supported_pipeline_and_corpus_version():
    evaluator = OfflineRagEvaluator(execute_case=lambda case: _execution())
    case = _case(10)

    with pytest.raises(ValueError, match="pipeline"):
        evaluator.evaluate((case,), pipeline="auto", corpus_version="public-knowledge-20260814")
    with pytest.raises(ValueError, match="corpus_version"):
        evaluator.evaluate((case,), pipeline="v2", corpus_version=" ")


def test_corpus_version_mismatch_is_a_release_blocker_without_leaking_case_query():
    evaluator = OfflineRagEvaluator(
        execute_case=lambda case: replace(
            _execution(),
            corpus_version="stale-public-knowledge",
        )
    )

    report = evaluator.evaluate(
        (_case(11),),
        pipeline="v2",
        corpus_version="public-knowledge-20260814",
    )

    assert report.outcomes[0].failure_stage == "version"
    assert report.outcomes[0].notes == ("CORPUS_VERSION_MISMATCH",)
    assert report.release_blockers == ("CORPUS_VERSION_MISMATCH",)


def test_persistence_stores_safe_summary_without_case_query_or_reference_content(app):
    from app import db
    from app.models.qa import RagEvalCase, RagEvaluationResult, RagEvaluationRun
    from app.services.rag_core.evaluation_persistence import persist_evaluation_report

    case_model = RagEvalCase(
        query="raw query must stay out of evaluation storage",
        expected_doc_ids=["doc-a"],
        expected_status="supported",
        category="concept",
        difficulty="medium",
        is_active=True,
    )
    db.session.add(case_model)
    db.session.commit()
    evaluator = OfflineRagEvaluator(execute_case=lambda case: _execution())
    report = evaluator.evaluate(
        (_case(case_model.id),),
        pipeline="v2",
        corpus_version="public-knowledge-20260814",
    )

    run_id = persist_evaluation_report(
        report,
        report_path="rag_report_persistence_test.json",
    )
    stored_run = db.session.get(RagEvaluationRun, run_id)
    stored_result = db.session.query(RagEvaluationResult).filter_by(run_id=run_id).one()
    serialized = json.dumps(
        {
            "metrics": stored_run.metrics_json,
            "retrieval": stored_result.retrieval_metrics_json,
            "citation": stored_result.citation_metrics_json,
            "answer": stored_result.answer_metrics_json,
            "notes": stored_result.notes,
        },
        ensure_ascii=False,
    )

    assert stored_run.report_path == "rag_report_persistence_test.json"
    assert "raw query" not in serialized
    assert "Title doc-a" not in serialized