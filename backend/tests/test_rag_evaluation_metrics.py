# -*- coding: utf-8 -*-
"""?? RAG ????????????"""
from __future__ import annotations

import pytest

from app.services.rag_core.contracts import CitationManifest, EvidenceReference
from app.services.rag_core.evaluation_metrics import (
    citation_determinism_metrics,
    evidence_pack_metrics,
    percentile,
    retrieval_metrics,
)


def _reference(citation_id: str, document_id: str, source: str = "public") -> EvidenceReference:
    return EvidenceReference(
        citation_id=citation_id,
        document_id=document_id,
        title=f"Title {document_id}",
        source=source,
        start_line=1,
        end_line=2,
    )


def test_retrieval_metrics_deduplicate_candidates_and_score_multiple_relevant_documents():
    metrics = retrieval_metrics(
        expected_document_ids=("doc-a", "doc-b"),
        candidate_document_ids=("noise", "doc-a", "doc-a", "doc-c"),
    )

    assert metrics["judged"] is True
    assert metrics["recall_at_20"] == pytest.approx(0.5)
    assert metrics["recall_at_40"] == pytest.approx(0.5)
    assert metrics["mrr_at_20"] == pytest.approx(0.5)
    assert metrics["ndcg_at_10"] == pytest.approx(0.3869, abs=0.0001)
    assert metrics["first_relevant_rank"] == 2


def test_retrieval_metrics_marks_unjudged_cases_without_turning_them_into_false_zeroes():
    metrics = retrieval_metrics(
        expected_document_ids=(),
        candidate_document_ids=("doc-a",),
    )

    assert metrics == {
        "judged": False,
        "recall_at_20": None,
        "recall_at_40": None,
        "mrr_at_20": None,
        "ndcg_at_10": None,
        "first_relevant_rank": None,
    }


def test_evidence_pack_metrics_distinguishes_coverage_noise_diversity_and_budget():
    metrics = evidence_pack_metrics(
        expected_document_ids=("doc-a", "doc-b"),
        references=(
            _reference("C1", "doc-a", "source-a"),
            _reference("C2", "noise", "source-b"),
            _reference("C3", "doc-a", "source-a"),
        ),
        token_count=250,
        token_budget=500,
    )

    assert metrics["expected_evidence_coverage"] == pytest.approx(0.5)
    assert metrics["context_precision"] == pytest.approx(0.5)
    assert metrics["noise_ratio"] == pytest.approx(0.5)
    assert metrics["source_diversity"] == pytest.approx(2 / 3)
    assert metrics["token_utilization"] == pytest.approx(0.5)
    assert metrics["reference_count"] == 3


def test_citation_determinism_rejects_unknown_claim_citations_and_unsafe_negative_status():
    manifest = CitationManifest(
        references=(_reference("C1", "doc-a"),),
        claim_citations={
            "verified claim": ("C1",),
            "forged claim": ("C999",),
        },
    )

    metrics = citation_determinism_metrics(
        manifest=manifest,
        actual_status="supported",
        expected_status="insufficient_evidence",
        status_observable=True,
        citation_observable=True,
    )

    assert metrics["unknown_citation_count"] == 1
    assert metrics["citations_belong_to_pack"] is False
    assert metrics["status_matches_expected"] is False
    assert metrics["unsafe_supported_negative"] is True
    assert metrics["is_deterministic"] is False


def test_citation_determinism_accepts_expected_insufficient_without_fabricated_citations():
    metrics = citation_determinism_metrics(
        manifest=CitationManifest(references=()),
        actual_status="insufficient_evidence",
        expected_status="insufficient_evidence",
        status_observable=True,
        citation_observable=True,
    )

    assert metrics["status_matches_expected"] is True
    assert metrics["is_deterministic"] is True
    assert metrics["unknown_citation_count"] == 0


def test_percentile_uses_linear_interpolation_and_handles_empty_input():
    assert percentile((10, 20, 30, 40, 50), 0.5) == pytest.approx(30)
    assert percentile((10, 20, 30, 40, 50), 0.95) == pytest.approx(48)
    assert percentile((), 0.95) is None
