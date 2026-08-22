# -*- coding: utf-8 -*-
"""生产公共知识库评测集（production_rag_eval_v1）的结构与审计约束测试。

该数据集由 `app/scripts/generate_rag_eval_from_corpus.py` 从真实语料导出
快照确定性生成；本测试保证其提交物始终满足：

- 规模与覆盖：足够多的用例、覆盖足够多的不同真实文档；
- 证据完整：每条 supported 用例都带真实索引的 chunk_id 与行号；
- 无正文泄漏：只允许小型 must_contain 锚句，不允许大段语料入库；
- 可复现：case_key 稳定唯一、查询不重复、字段自洽。
"""
from __future__ import annotations

import re

from app.services.rag_core.datasets import (
    PRODUCTION_CORPUS_VERSION,
    PRODUCTION_EVALUATION_CASES,
    build_production_evaluation_cases,
)
from app.services.rag_core.evaluation_contracts import EvaluationCase
from app.services.rag_core.citation_manifest import DEFAULT_PUBLIC_CORPUS_VERSION

MIN_CASES = 250
MIN_DISTINCT_DOCS = 250
MAX_ANCHOR_LEN = 120

_CHUNK_ID_PATTERN = re.compile(r"^doc_(\d+)_chunk_(\d+)$")


def _cases():
    return PRODUCTION_EVALUATION_CASES


def test_dataset_meets_scale_and_coverage():
    cases = _cases()
    assert len(cases) >= MIN_CASES
    distinct_docs = {case.expected_document_ids[0] for case in cases}
    assert len(distinct_docs) >= MIN_DISTINCT_DOCS


def test_case_keys_are_stable_unique_and_prefixed():
    cases = _cases()
    keys = [case.case_key for case in cases]
    assert len(set(keys)) == len(keys)
    assert all(key.startswith("prag-") for key in keys)


def test_queries_are_unique_and_never_leak_anchor_text():
    cases = _cases()
    queries = [case.query for case in cases]
    assert len(set(queries)) == len(queries)
    for case in cases:
        assert case.query.strip()
        for evidence in case.expected_evidence:
            anchor = evidence["must_contain"]
            assert anchor not in case.query


def test_every_case_is_supported_with_single_real_index_evidence():
    cases = _cases()
    for case in cases:
        assert isinstance(case, EvaluationCase)
        assert case.category == "retrieval_supported"
        assert case.difficulty in {"easy", "medium", "hard"}
        assert case.expected_status == "supported"
        assert len(case.expected_evidence) == 1
        assert len(case.expected_document_ids) == 1
        evidence = case.expected_evidence[0]
        assert evidence["document_id"] == case.expected_document_ids[0]
        assert evidence["corpus_version"] == PRODUCTION_CORPUS_VERSION
        assert evidence["role"] == "primary"
        assert evidence["title"].strip()
        # chunk_id 必须与 document_id 自洽（doc_{id}_chunk_{n}）。
        match = _CHUNK_ID_PATTERN.match(evidence["chunk_id"])
        assert match, f"bad chunk_id: {evidence['chunk_id']}"
        assert match.group(1) == str(evidence["document_id"])
        assert int(match.group(2)) >= 0
        # 行号必须为正且区间有效。
        assert isinstance(evidence["start_line"], int)
        assert isinstance(evidence["end_line"], int)
        assert evidence["start_line"] >= 1
        assert evidence["end_line"] >= evidence["start_line"]


def test_anchor_fragments_are_small_single_line_audits():
    cases = _cases()
    anchors = set()
    for case in cases:
        anchor = case.expected_evidence[0]["must_contain"]
        assert isinstance(anchor, str)
        assert "\n" not in anchor
        assert 10 <= len(anchor) <= MAX_ANCHOR_LEN
        assert anchor not in anchors, "锚句不得跨用例重复"
        anchors.add(anchor)


def test_tags_mark_auto_generated_provenance():
    for case in _cases():
        assert "auto_generated" in case.tags
        assert "production_corpus" in case.tags


def test_corpus_version_matches_public_citation_default():
    assert PRODUCTION_CORPUS_VERSION == DEFAULT_PUBLIC_CORPUS_VERSION


def test_builder_rebuilds_identical_sequence():
    rebuilt = build_production_evaluation_cases()
    assert len(rebuilt) == len(_cases())
    for built, cached in zip(rebuilt, _cases()):
        assert built.case_key == cached.case_key
        assert built.query == cached.query
        assert built.expected_evidence == cached.expected_evidence


def test_case_ids_are_sequential():
    cases = _cases()
    assert [case.case_id for case in cases] == list(range(1, len(cases) + 1))
