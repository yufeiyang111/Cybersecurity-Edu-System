"""RAG 离线评估脚本：对 rag_eval_cases 评估集计算检索质量指标。

用法（backend 目录下）：
    .venv\\Scripts\\python.exe -m app.scripts.rag_evaluate

指标：
    hit@1 / hit@3 / hit@5 / MRR（基于期望命中文档）
评估前会先统计评估集数量；无评估集时提示先导入。
"""
from __future__ import annotations

import json

from app import create_app, db
from app.models.qa import RagEvalCase
from app.services.enhanced_rag_engine import get_rag_engine


def _expected_ids(case: RagEvalCase) -> set[str]:
    raw = case.expected_doc_ids
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return set()
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return set()


def _retrieved_ids(engine, query: str, top_k: int) -> list[str]:
    docs = engine.retrieve(query, top_k=top_k)
    return [str(doc["id"]) for doc in docs]


def evaluate(top_k: int = 5) -> dict:
    # 注意：RagEvalCase 有名为 query 的列，需用 session 查询（避开 Model.query 遮蔽）
    cases = db.session.query(RagEvalCase).all()
    if not cases:
        return {"error": "评估集为空：请先向 rag_eval_cases 表导入评测用例"}

    engine = get_rag_engine()
    hits = {1: 0, 3: 0, 5: 0}
    mrr_sum = 0.0
    details = []

    for case in cases:
        expected = _expected_ids(case)
        if not expected:
            continue
        retrieved = _retrieved_ids(engine, case.query, top_k=5)
        for k in (1, 3, 5):
            if any(doc_id in expected for doc_id in retrieved[:k]):
                hits[k] += 1
        for rank, doc_id in enumerate(retrieved, start=1):
            if doc_id in expected:
                mrr_sum += 1.0 / rank
                break
        details.append({
            "query": case.query,
            "expected": sorted(expected),
            "retrieved_top5": retrieved,
            "hit@5": any(doc_id in expected for doc_id in retrieved[:5]),
        })

    total = max(1, len(cases))
    return {
        "cases": len(cases),
        "hit@1": round(hits[1] / total, 4),
        "hit@3": round(hits[3] / total, 4),
        "hit@5": round(hits[5] / total, 4),
        "mrr": round(mrr_sum / total, 4),
        "details": details,
    }


def main() -> None:
    app = create_app()
    with app.app_context():
        report = evaluate()
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
