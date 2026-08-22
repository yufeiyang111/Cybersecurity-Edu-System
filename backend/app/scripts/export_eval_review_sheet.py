# -*- coding: utf-8 -*-
"""把 RAG 评测集导出为「人工审批清单」（CSV）与机器可读副本（JSONL）。

产物（写入 ``backend/data/``，已 gitignore）：

- ``eval_review_<dataset>.csv``：UTF-8 BOM，Excel 直接打开不乱码。
  列：case_key / dataset / query / difficulty / document_id / doc_title /
  evidence_lines / anchor_snippet / review_status / reviewer_note。
  用户把 ``review_status`` 改为 approved / rejected（默认 pending），
  并可在 reviewer_note 写理由；
- ``eval_review_<dataset>.jsonl``：同内容的机器可读版本。

用法（在 backend/ 下）::

    venv\\Scripts\\python.exe -m app.scripts.export_eval_review_sheet
    venv\\Scripts\\python.exe -m app.scripts.export_eval_review_sheet --dataset curated
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from app.services.rag_core.datasets import (
    EVALUATION_CASES,
    PRODUCTION_CURATED_EVALUATION_CASES,
    PRODUCTION_EVALUATION_CASES,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = BACKEND_ROOT / "data" / "评测集"

DATASETS = {
    "curated": PRODUCTION_CURATED_EVALUATION_CASES,
    "auto": PRODUCTION_EVALUATION_CASES,
    "v1": EVALUATION_CASES,
}

CSV_FIELDS = [
    "case_key",
    "dataset",
    "query",
    "difficulty",
    "document_id",
    "doc_title",
    "evidence_lines",
    "anchor_snippet",
    "review_status",
    "reviewer_note",
]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="导出评测集人工审批清单（CSV + JSONL）",
    )
    parser.add_argument(
        "--dataset",
        choices=(*DATASETS, "all"),
        default="all",
        help="要导出的数据集（默认 all）",
    )
    parser.add_argument("--out-dir", default=None, help="输出目录（默认 backend/data）")
    return parser


def _row_of(dataset: str, case) -> Dict[str, Any]:
    evidence = case.expected_evidence[0] if case.expected_evidence else {}
    anchor = str(evidence.get("must_contain") or "")
    lines = ""
    if evidence:
        lines = f"{evidence.get('start_line')}-{evidence.get('end_line')}"
    return {
        "case_key": case.case_key,
        "dataset": dataset,
        "query": case.query,
        "difficulty": case.difficulty,
        "document_id": ",".join(case.expected_document_ids),
        "doc_title": str(evidence.get("title") or ""),
        "evidence_lines": lines,
        "anchor_snippet": anchor[:80],
        "review_status": "pending",
        "reviewer_note": "",
    }


def build_rows(dataset: str) -> List[Dict[str, Any]]:
    return [_row_of(dataset, case) for case in DATASETS[dataset]]


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(rows: List[Dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = build_argument_parser().parse_args()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = list(DATASETS) if args.dataset == "all" else [args.dataset]
    for dataset in selected:
        rows = build_rows(dataset)
        csv_path = out_dir / f"eval_review_{dataset}.csv"
        jsonl_path = out_dir / f"eval_review_{dataset}.jsonl"
        write_csv(rows, csv_path)
        write_jsonl(rows, jsonl_path)
        print(
            json.dumps(
                {
                    "dataset": dataset,
                    "cases": len(rows),
                    "csv": str(csv_path),
                    "jsonl": str(jsonl_path),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
