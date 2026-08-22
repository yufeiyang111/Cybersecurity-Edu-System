# -*- coding: utf-8 -*-
"""人工策展全覆盖生产评测集（production_rag_eval_curated_v1）的审计约束测试。

数据集由 build_curated_rag_eval 从 ``curated_query_map``（LLM 为每篇真实文档
手写的查询表）编译生成：query 非模板；锚句经导出快照逐字校验并回填真实行号。
"""
from __future__ import annotations

import re

from app.services.rag_core.citation_manifest import DEFAULT_PUBLIC_CORPUS_VERSION
from app.services.rag_core.datasets import (
    PRODUCTION_CURATED_EVALUATION_CASES,
    PRODUCTION_EVALUATION_CASES,
    build_production_curated_evaluation_cases,
)
from app.services.rag_core.datasets.curated_query_map import CURATED_QUERY_MAP
from app.services.rag_core.evaluation_contracts import EvaluationCase

MIN_CASES = 1000
_CHUNK_ID_PATTERN = re.compile(r"^doc_(\d+)_chunk_(\d+)$")


def _cases():
    return PRODUCTION_CURATED_EVALUATION_CASES


def test_full_corpus_coverage():
    cases = _cases()
    assert len(cases) >= MIN_CASES
    # 查询表覆盖全部语料文档；构建时仅允许跳过「无索引分块」的极少数文档。
    assert len(CURATED_QUERY_MAP) >= len(cases)
    assert len(cases) >= len(CURATED_QUERY_MAP) - 5
    docs = {case.expected_document_ids[0] for case in cases}
    assert len(docs) == len(cases), "每条用例应锚定不同的真实文档"


def test_case_keys_are_sequential_and_stable():
    cases = _cases()
    keys = [case.case_key for case in cases]
    expected = [f"curag-{index + 1:04d}" for index in range(len(keys))]
    assert keys == expected


def test_queries_unique_natural_and_disjoint_from_auto_set():
    cases = _cases()
    queries = [case.query for case in cases]
    assert len(set(queries)) == len(queries)
    auto_queries = {case.query for case in PRODUCTION_EVALUATION_CASES}
    assert not (set(queries) & auto_queries)
    for query in queries:
        assert 8 <= len(query) <= 80
        # 自动模板句式禁止出现在策展集。
        assert "的核心要点是什么" not in query
        assert "主要涉及哪些方面" not in query


def test_every_case_has_single_verified_real_index_evidence():
    for case in _cases():
        assert isinstance(case, EvaluationCase)
        assert case.category == "retrieval_supported"
        assert case.difficulty in {"easy", "medium", "hard"}
        assert case.expected_status == "supported"
        assert len(case.expected_evidence) == 1
        evidence = case.expected_evidence[0]
        assert evidence["document_id"] == case.expected_document_ids[0]
        assert evidence["corpus_version"] == DEFAULT_PUBLIC_CORPUS_VERSION
        assert evidence["role"] == "primary"
        assert evidence["title"].strip()
        match = _CHUNK_ID_PATTERN.match(evidence["chunk_id"])
        assert match, f"bad chunk_id: {evidence['chunk_id']}"
        assert match.group(1) == str(evidence["document_id"])
        assert int(match.group(2)) >= 0
        assert isinstance(evidence["start_line"], int)
        assert isinstance(evidence["end_line"], int)
        assert evidence["start_line"] >= 1
        assert evidence["end_line"] >= evidence["start_line"]
        anchor = evidence["must_contain"]
        assert "\n" not in anchor
        assert 6 <= len(anchor) <= 120
        assert anchor not in case.query


def test_difficulty_distribution_covers_all_levels():
    difficulties = {case.difficulty for case in _cases()}
    assert difficulties == {"easy", "medium", "hard"}


def test_tags_mark_llm_curated_provenance():
    for case in _cases():
        assert "llm_curated" in case.tags
        assert "production_corpus" in case.tags


def test_builder_rebuilds_identical_sequence():
    rebuilt = build_production_curated_evaluation_cases()
    cached = _cases()
    assert len(rebuilt) == len(cached)
    for built, old in zip(rebuilt, cached):
        assert built.case_key == old.case_key
        assert built.query == old.query
        assert built.expected_evidence == old.expected_evidence
