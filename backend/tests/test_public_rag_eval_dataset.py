# -*- coding: utf-8 -*-
"""公共知识库 RAG v1 评测集的静态审计与 gold evidence 可溯源性测试。

这些测试不依赖 live Qdrant / Embedding / Reranker / LLM Provider，仅使用
项目既有 `SAMPLE_KNOWLEDGE_ITEMS` 与真实 `chunk_text`，验证：
- 数据规模、分类、难度、稳定 ID、去重；
- 每条 supported case 的 gold evidence 能映射到真实文档与真实行范围；
- insufficient / adversarial case 不携带任何伪造 evidence；
- 断言只使用受控字段（ID / 标题 / 行范围），不含正文、Prompt 或 query。
"""
from __future__ import annotations

from app.services.rag_core.datasets import (
    CORPUS_VERSION,
    RAW_SPECS,
    build_evaluation_cases,
)
from app.services.rag_core.datasets.corpus_fixture import (
    build_sample_corpus,
    chunk_corpus,
    locate_evidence,
)
from app.services.rag_core.evaluation_contracts import EvaluationCase

EXPECTED_EVIDENCE_KEYS = {
    "document_id",
    "title",
    "chunk_id",
    "start_line",
    "end_line",
    "corpus_version",
    "role",
}


def _cases():
    return build_evaluation_cases()


def test_dataset_meets_minimum_size_with_required_structure():
    cases = _cases()
    assert len(cases) >= 60
    assert len(RAW_SPECS) == len(cases)
    for case in cases:
        assert isinstance(case, EvaluationCase)
        assert case.category in {
            "retrieval_supported",
            "insufficient_evidence",
            "adversarial_or_boundary",
        }
        assert case.difficulty in {"easy", "medium", "hard"}
        assert case.expected_status in {"supported", "insufficient_evidence"}


def test_case_keys_are_stable_and_unique():
    cases = _cases()
    keys = [case.case_key for case in cases]
    assert len(set(keys)) == len(keys)
    assert all(k.strip() for k in keys)


def test_at_least_20_percent_are_insufficient_or_adversarial():
    cases = _cases()
    negative = [
        c
        for c in cases
        if c.category in {"insufficient_evidence", "adversarial_or_boundary"}
    ]
    assert len(negative) >= len(cases) * 0.2


def test_supported_cases_resolve_to_real_corpus_evidence():
    corpus = build_sample_corpus()
    chunks = chunk_corpus(corpus)
    cases = build_evaluation_cases(corpus=corpus, chunks=chunks)
    spec_by_key = {s["case_key"]: s for s in RAW_SPECS}

    supported = [c for c in cases if c.category == "retrieval_supported"]
    assert supported, "must have supported cases to validate gold evidence"
    assert len(supported) >= 10

    for case in supported:
        assert case.expected_status == "supported"
        assert case.expected_document_ids
        assert case.expected_evidence
        assert case.tags
        assert len(case.expected_evidence) == len(spec_by_key[case.case_key]["evidence"])

        for evidence_spec, evidence in zip(
            spec_by_key[case.case_key]["evidence"], case.expected_evidence
        ):
            # 关键：用真实 chunker 在真实内容上重新定位，断言与存储 gold evidence 完全一致。
            located = locate_evidence(
                corpus, chunks, evidence_spec["document_id"], evidence_spec["must_contain"]
            )
            assert located["document_id"] == evidence["document_id"]
            assert located["title"] == evidence["title"]
            assert located["chunk_id"] == evidence["chunk_id"]
            assert located["start_line"] == evidence["start_line"]
            assert located["end_line"] == evidence["end_line"]
            assert located["corpus_version"] == CORPUS_VERSION

            assert evidence["document_id"] in corpus
            assert evidence["title"] == corpus[evidence["document_id"]]["title"]
            assert evidence["chunk_id"]
            assert isinstance(evidence["start_line"], int) and isinstance(evidence["end_line"], int)
            assert 0 < evidence["start_line"] <= evidence["end_line"]


def test_insufficient_and_adversarial_have_no_fabricated_evidence():
    cases = _cases()
    for case in cases:
        if case.category in {"insufficient_evidence", "adversarial_or_boundary"}:
            assert case.expected_status == "insufficient_evidence"
            assert case.expected_document_ids == ()
            assert case.expected_evidence == ()


def test_expected_evidence_never_carries_body_prompt_or_query():
    cases = _cases()
    for case in cases:
        for evidence in case.expected_evidence:
            assert set(evidence.keys()) <= EXPECTED_EVIDENCE_KEYS
            assert "content" not in evidence
            assert "text" not in evidence
            assert "prompt" not in evidence
            assert "query" not in evidence


def test_dataset_covers_multiple_corpus_documents():
    cases = _cases()
    covered = {
        doc_id for case in cases for doc_id in case.expected_document_ids
    }
    assert len(covered) >= 10
