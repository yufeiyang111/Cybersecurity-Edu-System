# -*- coding: utf-8 -*-
"""Boundary tests for the local release-gate CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.scripts import rag_release_gate


def _report(pipeline: str) -> dict:
    return {
        "schema_version": "enterprise-rag-eval-v1",
        "pipeline": pipeline,
        "corpus_version": "public-knowledge-20260814",
        "case_count": 200,
        "metrics": {
            "retrieval": {"recall_at_20": 0.7, "ndcg_at_10": 0.6},
            "evidence": {
                "expected_evidence_coverage": 0.65,
                "context_precision": 0.55,
            },
            "runtime": {"retrieval_p95_ms": 100},
        },
        "by_category": {
            "insufficient": {"citation": {"unsafe_supported_negative_count": 0}},
            "injection": {"citation": {"unsafe_supported_negative_count": 0}},
        },
        "release_blockers": [],
        "outcomes": [{"case_id": case_id} for case_id in range(1, 201)],
    }


def _write_report(root: Path, name: str, payload: dict) -> None:
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def test_cli_parser_requires_both_report_names():
    parser = rag_release_gate.build_argument_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args(
        ["--legacy-report", "rag_report_legacy.json", "--v2-report", "rag_report_v2.json"]
    )
    assert args.legacy_report == "rag_report_legacy.json"
    assert args.v2_report == "rag_report_v2.json"


def test_cli_writes_only_sanitized_result_to_backend_root(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_release_gate, "BACKEND_ROOT", tmp_path)
    legacy = _report("legacy")
    v2 = _report("v2")
    v2["metrics"]["retrieval"]["recall_at_20"] = 0.75
    v2["metrics"]["retrieval"]["ndcg_at_10"] = 0.65
    v2["outcomes"][0]["query"] = "private query"
    _write_report(tmp_path, "rag_report_legacy.json", legacy)
    _write_report(tmp_path, "rag_report_v2.json", v2)

    payload, exit_code = rag_release_gate.run_release_gate(
        legacy_report_name="rag_report_legacy.json",
        v2_report_name="rag_report_v2.json",
        output_name="rag_release_gate_compare.json",
    )
    saved = (tmp_path / "rag_release_gate_compare.json").read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["result_file"] == "rag_release_gate_compare.json"
    assert "private query" not in saved
    assert "case_id" not in saved


def test_cli_no_write_and_path_traversal_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_release_gate, "BACKEND_ROOT", tmp_path)
    _write_report(tmp_path, "rag_report_legacy.json", _report("legacy"))
    _write_report(tmp_path, "rag_report_v2.json", _report("v2"))

    payload, _ = rag_release_gate.run_release_gate(
        legacy_report_name="rag_report_legacy.json",
        v2_report_name="rag_report_v2.json",
        write_output=False,
    )

    assert "result_file" not in payload
    with pytest.raises(ValueError, match="invalid report file name"):
        rag_release_gate.load_report("../rag_report_legacy.json")
    with pytest.raises(ValueError, match="invalid output file name"):
        rag_release_gate.write_result(payload, "../rag_release_gate_result.json")


def test_cli_rejects_malformed_or_non_object_report(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_release_gate, "BACKEND_ROOT", tmp_path)
    (tmp_path / "rag_report_bad.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="report must be a JSON object"):
        rag_release_gate.load_report("rag_report_bad.json")
