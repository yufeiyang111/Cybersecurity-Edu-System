# -*- coding: utf-8 -*-
"""评测套件脚本纯函数的单元测试（审批过滤 / 文件名 / 导出行构造）。"""
from __future__ import annotations

import pytest

from app.scripts.export_eval_review_sheet import build_rows
from app.scripts.run_rag_eval_suite import (
    DATASETS,
    filter_by_review,
    load_review_status,
    report_filename,
)
from app.services.rag_core.evaluation_contracts import EvaluationCase


def _case(key: str) -> EvaluationCase:
    return EvaluationCase(
        case_id=1,
        case_key=key,
        category="retrieval_supported",
        difficulty="easy",
        expected_document_ids=("1",),
        expected_status="supported",
        review_note="",
        query=f"q-{key}",
    )


def test_load_review_status_reads_valid_and_skips_invalid(tmp_path):
    path = tmp_path / "review.csv"
    path.write_text(
        "case_key,review_status\n"
        "curag-0001,approved\n"
        "curag-0002,REJECTED\n"
        "curag-0003,bogus\n"
        ",approved\n",
        encoding="utf-8-sig",
    )
    status = load_review_status(path)
    assert status == {"curag-0001": "approved", "curag-0002": "rejected"}


def test_load_review_status_missing_file_returns_empty(tmp_path):
    assert load_review_status(tmp_path / "nope.csv") == {}


def test_filter_by_review_default_only_approved():
    cases = (_case("a"), _case("b"), _case("c"), _case("d"))
    status = {"a": "approved", "b": "rejected", "c": "pending"}
    selected, counts = filter_by_review(cases, status, include_pending=False)
    assert [c.case_key for c in selected] == ["a"]
    assert counts == {
        "approved": 1,
        "pending": 1,
        "rejected": 1,
        "unreviewed": 1,
    }


def test_filter_by_review_include_pending_adds_pending_and_unreviewed():
    cases = (_case("a"), _case("b"), _case("c"), _case("d"))
    status = {"a": "approved", "b": "rejected", "c": "pending"}
    selected, _ = filter_by_review(cases, status, include_pending=True)
    assert [c.case_key for c in selected] == ["a", "c", "d"]


def test_report_filename_rejects_bad_tag():
    assert report_filename("run_01", "curated") == "rag_report_run_01_curated.json"
    with pytest.raises(ValueError):
        report_filename("../evil", "curated")


def test_build_rows_marks_pending_and_fills_evidence():
    rows = build_rows("v1")
    assert len(rows) == len(DATASETS["v1"])
    first = rows[0]
    assert first["review_status"] == "pending"
    assert first["dataset"] == "v1"
    assert first["query"]
    assert first["document_id"]
