# -*- coding: utf-8 -*-
"""?????? RAG ???? SQL ????????"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "backend" / "rag_eval_cases.jsonl"
SEED_PATH = ROOT / "database" / "seed_rag_eval_cases.sql"
REQUIRED_CATEGORIES = {
    "concept",
    "identifier",
    "defense",
    "multihop",
    "alias",
    "insufficient",
    "conflict",
    "injection",
}
ALLOWED_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "degraded",
}


def _rows() -> list[dict]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_evaluation_dataset_has_200_plus_active_auditable_cases_without_document_bodies():
    rows = _rows()
    active_rows = [row for row in rows if row["is_active"]]

    assert len(active_rows) >= 200
    assert REQUIRED_CATEGORIES <= {row["category"] for row in active_rows}
    assert {row["difficulty"] for row in active_rows} == {"easy", "medium", "hard"}
    assert len({row["case_key"] for row in rows}) == len(rows)

    for row in active_rows:
        assert set(row) >= {
            "case_key",
            "query",
            "category",
            "difficulty",
            "expected_doc_ids",
            "expected_evidence",
            "expected_status",
            "review_note",
            "is_active",
        }
        assert row["expected_status"] in ALLOWED_STATUSES
        assert row["review_note"].strip()
        assert len(row["query"]) <= 500
        assert "expected_text" not in row
        assert "content" not in row
        assert "prompt" not in row
        if row["expected_status"] == "supported":
            assert row["expected_doc_ids"]
            assert row["expected_evidence"]
        else:
            assert row["expected_status"] != "supported"


def test_seed_sql_is_idempotent_and_covers_every_version_controlled_case():
    rows = _rows()
    seed = SEED_PATH.read_text(encoding="utf-8")

    assert "expected_evidence_json" in seed
    assert "expected_status" in seed
    assert "difficulty" in seed
    assert "is_active" in seed
    assert "WHERE NOT EXISTS" in seed
    assert seed.count("-- eval-case:") == len(rows)
    for row in rows:
        assert f"-- eval-case: {row['case_key']}" in seed
