# -*- coding: utf-8 -*-
"""检索消融实验：混合检索（dense + BM25，RRF 融合）对比纯向量检索（dense-only）。

同一批评测 query、同一 embedding、同一 Qdrant collection 下，
分别执行两条召回路径并统计 Recall@1 / Recall@5 / MRR，
量化「BM25 词法路 + RRF 融合」相对纯向量检索的真实增益。

只读实验：仅调用 embedding 与 Qdrant 查询，不触达 LLM / 重排。

用法（在 backend/ 下）::

    venv\\Scripts\\python.exe -m app.scripts.ablation_retrieval --dataset curated
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app import create_app
from app.services.rag_core.datasets import (
    EVALUATION_CASES,
    PRODUCTION_CURATED_EVALUATION_CASES,
    PRODUCTION_EVALUATION_CASES,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = BACKEND_ROOT / "data"

DATASETS = {
    "curated": PRODUCTION_CURATED_EVALUATION_CASES,
    "auto": PRODUCTION_EVALUATION_CASES,
    "v1": EVALUATION_CASES,
}

_PROGRESS_EVERY = 100


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="混合检索 vs 纯向量检索消融实验")
    parser.add_argument("--dataset", choices=tuple(DATASETS), default="curated")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out", default=None, help="结果 JSON 路径")
    return parser


def _rank_of_first_hit(hit_ids: List[str], expected: set) -> int:
    for rank, doc_id in enumerate(hit_ids, start=1):
        if doc_id in expected:
            return rank
    return 0


def _as_vector(embedding_result: Any) -> List[float]:
    """encode_query 返回 np.ndarray（可能为二维），展平为一维 float 列表。"""
    import numpy as np

    return np.asarray(embedding_result, dtype=float).ravel().tolist()


def run(dataset: str, top_k: int, limit: int | None) -> Dict[str, Any]:
    from app.services.secbert_embedding import get_embedding_service
    from app.services.vector_stores.factory import get_vector_backend

    cases = [c for c in DATASETS[dataset] if c.expected_status == "supported"]
    if limit is not None and limit > 0:
        cases = cases[:limit]
    embedding = get_embedding_service()
    backend = get_vector_backend()

    rows: List[Dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        expected = set(case.expected_document_ids)
        vector = _as_vector(embedding.encode_query(case.query))
        hybrid_hits = backend.hybrid_search(
            vector=vector,
            text=case.query,
            where=None,
            top_k=top_k,
        )
        dense_hits = backend.search(
            vector=vector,
            where=None,
            top_k=top_k,
        )
        hybrid_ids = [
            str((h.metadata or {}).get("doc_id") or h.id) for h in hybrid_hits
        ]
        dense_ids = [
            str((h.metadata or {}).get("doc_id") or h.id) for h in dense_hits
        ]
        rows.append(
            {
                "case_key": case.case_key,
                "query": case.query,
                "expected": sorted(expected),
                "hybrid_ids": hybrid_ids,
                "dense_ids": dense_ids,
                "hybrid_rank": _rank_of_first_hit(hybrid_ids, expected),
                "dense_rank": _rank_of_first_hit(dense_ids, expected),
            }
        )
        if index % _PROGRESS_EVERY == 0:
            print(f"progress {index}/{len(cases)}", flush=True)

    def _metrics(ranks: List[int]) -> Dict[str, float]:
        n = max(1, len(ranks))
        return {
            "recall_at_1": sum(1 for r in ranks if r == 1) / n,
            "recall_at_5": sum(1 for r in ranks if 1 <= r <= 5) / n,
            "mrr": sum(1.0 / r for r in ranks if r > 0) / n,
        }

    hybrid_metrics = _metrics([r["hybrid_rank"] for r in rows])
    dense_metrics = _metrics([r["dense_rank"] for r in rows])
    return {
        "dataset": dataset,
        "cases": len(rows),
        "top_k": top_k,
        "generated_at": datetime.utcnow().isoformat(),
        "hybrid": hybrid_metrics,
        "dense_only": dense_metrics,
        "delta_recall_at_1": round(
            hybrid_metrics["recall_at_1"] - dense_metrics["recall_at_1"], 4
        ),
        "delta_mrr": round(hybrid_metrics["mrr"] - dense_metrics["mrr"], 4),
        "rows": rows,
    }


def main() -> None:
    args = build_argument_parser().parse_args()
    out_path = (
        Path(args.out).resolve()
        if args.out
        else DEFAULT_OUT_DIR / f"ablation_{args.dataset}.json"
    )
    app = create_app()
    with app.app_context():
        result = run(args.dataset, args.top_k, args.limit)
    result.pop("rows")
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
