# -*- coding: utf-8 -*-
"""RAG 离线评测命令：兼容 legacy 基线，并提供企业评测报告。"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Iterable

from app import create_app, db
from app.models.qa import RagEvalCase
from app.services.enhanced_rag_engine import get_rag_engine
from app.services.rag_core.evaluation_contracts import EvaluationCase
from app.services.rag_core.evaluation_persistence import persist_evaluation_report
from app.services.rag_core.evaluation_runtime import (
    build_runtime_executor,
    evaluation_case_from_model,
)
from app.services.rag_core.evaluator import OfflineRagEvaluator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPORT_NAME = re.compile(r"^rag_report_[A-Za-z0-9_-]+\.json$")


def _expected_ids(case: RagEvalCase) -> set[str]:
    raw = case.expected_doc_ids
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return set()
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return set()


def _retrieved_ids(engine, query: str, top_k: int) -> list[str]:
    docs = engine.retrieve(query, top_k=top_k)
    return [str(doc["id"]) for doc in docs]


def evaluate(top_k: int = 5) -> dict:
    """保留原有 legacy 基线接口，供历史脚本和测试继续使用。"""
    cases = db.session.query(RagEvalCase).all()
    if not cases:
        return {"error": "评估集为空：请先向 rag_eval_cases 表导入评测用例"}

    engine = get_rag_engine()
    hits = {1: 0, 3: 0, 5: 0}
    mrr_sum = 0.0
    details = []
    judged_cases = 0
    for case in cases:
        expected = _expected_ids(case)
        if not expected:
            continue
        judged_cases += 1
        retrieved = _retrieved_ids(engine, case.query, top_k=top_k)
        for cutoff in (1, 3, 5):
            if any(doc_id in expected for doc_id in retrieved[:cutoff]):
                hits[cutoff] += 1
        for rank, doc_id in enumerate(retrieved, start=1):
            if doc_id in expected:
                mrr_sum += 1.0 / rank
                break
        details.append(
            {
                "case_id": case.id,
                "category": case.category,
                "hit_at_5": any(doc_id in expected for doc_id in retrieved[:5]),
            }
        )

    total = max(1, judged_cases)
    return {
        "cases": judged_cases,
        "hit@1": round(hits[1] / total, 4),
        "hit@3": round(hits[3] / total, 4),
        "hit@5": round(hits[5] / total, 4),
        "mrr": round(mrr_sum / total, 4),
        "details": details,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """企业评测必须显式选择 pipeline 和语料版本，避免不可比报告。"""
    parser = argparse.ArgumentParser(description="运行企业 RAG 离线评测")
    parser.add_argument("--pipeline", choices=("legacy", "v2"), required=True)
    parser.add_argument("--corpus-version", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-name", default=None)
    parser.add_argument("--no-persist", action="store_true")
    return parser


def run_enterprise_evaluation(
    *,
    pipeline: str,
    corpus_version: str,
    limit: int | None = None,
    report_name: str | None = None,
    persist: bool = True,
    cases: Iterable[EvaluationCase] | None = None,
    executor=None,
) -> dict:
    """执行指定策略并输出安全报告；测试可注入 case 和 executor，避免真实 HTTP。"""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    selected_cases = tuple(cases) if cases is not None else _active_cases(limit)
    if not selected_cases:
        raise ValueError("评测集为空：请先导入并激活 RAG 评测用例")

    execution_port = executor or build_runtime_executor(
        pipeline=pipeline,
        corpus_version=corpus_version,
    )
    report = OfflineRagEvaluator(execute_case=execution_port).evaluate(
        selected_cases,
        pipeline=pipeline,
        corpus_version=corpus_version,
    )
    normalized_name = _report_name(report_name, pipeline)
    saved_name = write_report(report, normalized_name)
    run_id = (
        persist_evaluation_report(report, report_path=saved_name)
        if persist
        else None
    )
    payload = report.to_report_dict()
    payload["report_file"] = saved_name
    payload["run_id"] = run_id
    return payload


def write_report(report, report_name: str) -> str:
    """仅写入已 gitignore 的安全评测摘要，不接受目录或任意文件名。"""
    if not _REPORT_NAME.fullmatch(report_name):
        raise ValueError("report_name must match rag_report_*.json")
    path = BACKEND_ROOT / report_name
    path.write_text(
        json.dumps(report.to_report_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return report_name


def _active_cases(limit: int | None) -> tuple[EvaluationCase, ...]:
    query = (
        db.session.query(RagEvalCase)
        .filter(RagEvalCase.is_active.is_(True))
        .order_by(RagEvalCase.id.asc())
    )
    if limit is not None:
        query = query.limit(limit)
    return tuple(evaluation_case_from_model(model) for model in query.all())


def _report_name(value: str | None, pipeline: str) -> str:
    if value is not None:
        normalized = value.strip()
        if not _REPORT_NAME.fullmatch(normalized):
            raise ValueError("report_name must match rag_report_*.json")
        return normalized
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"rag_report_{timestamp}_{pipeline}.json"


def main() -> None:
    args = build_argument_parser().parse_args()
    app = create_app()
    with app.app_context():
        report = run_enterprise_evaluation(
            pipeline=args.pipeline,
            corpus_version=args.corpus_version,
            limit=args.limit,
            report_name=args.report_name,
            persist=not args.no_persist,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
