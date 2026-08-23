# -*- coding: utf-8 -*-
"""一键运行 RAG 真实链路 QA 评测：按人工审批过滤用例并完整记录数据。

流程：
1. 从 ``datasets`` 包加载评测集（curated / auto / v1 / all）；
2. 若存在 ``backend/data/eval_review_<dataset>.csv`` 审批清单，则只跑
   ``approved`` 用例（``--include-pending`` 可临时放行 pending，
   ``rejected`` 永远跳过）；无清单时全量运行并在摘要中注明；
3. 通过 ``build_runtime_executor`` 构建真实链路执行器
   （真实 Embedding / Qdrant / LLM），逐题执行并捕获明细；
4. 写出两类产物（均在 gitignore 范围内）：
   - 汇总报告 ``backend/rag_report_<tag>_<dataset>.json``
   - 逐题明细 ``backend/data/eval_run_<tag>_<dataset>.jsonl``
     （含 query、期望文档、召回 Top5、hit/MRR、失败阶段、耗时等）。

用法（在 backend/ 下，需本机 Qdrant / .env 密钥就绪）::

    venv\\Scripts\\python.exe -m app.scripts.run_rag_eval_suite --dataset curated --limit 5
    venv\\Scripts\\python.exe -m app.scripts.run_rag_eval_suite --dataset all --tag full
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app import create_app
from app.services.llm.provider_selector import select_provider
from app.services.rag_core.datasets import (
    EVALUATION_CASES,
    PRODUCTION_CURATED_EVALUATION_CASES,
    PRODUCTION_EVALUATION_CASES,
)
from app.services.rag_core.evaluation_contracts import (
    EvaluationCase,
    EvaluationExecution,
)
from app.services.rag_core.evaluation_runtime import build_runtime_executor
from app.services.rag_core.evaluator import OfflineRagEvaluator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = BACKEND_ROOT / "data"
DEFAULT_REVIEW_DIR = BACKEND_ROOT / "data" / "评测集"
DEFAULT_CORPUS_VERSION = "knowledge_embeddings-v1"

DATASETS = {
    "curated": PRODUCTION_CURATED_EVALUATION_CASES,
    "auto": PRODUCTION_EVALUATION_CASES,
    "v1": EVALUATION_CASES,
}

_REPORT_NAME = re.compile(r"^rag_report_[A-Za-z0-9_-]+\.json$")
_SECRET_URL_PATTERN = re.compile(r"(\w+://)[^/@\s]+:[^@\s]+@")


def _sanitize(message: object) -> str:
    return _SECRET_URL_PATTERN.sub(r"\1***@...", str(message))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一键运行 RAG 真实链路 QA 评测")
    parser.add_argument(
        "--dataset",
        choices=(*DATASETS, "all"),
        default="curated",
        help="评测集（默认 curated；v1 锚定样例库 kb-*，仅适合离线自检，"
             "真实链路评测请用 curated / auto）",
    )
    parser.add_argument("--limit", type=int, default=None, help="每套数据集最多跑多少题")
    parser.add_argument(
        "--include-pending",
        action="store_true",
        help="审批清单中 pending 的用例也参与（rejected 始终跳过）",
    )
    parser.add_argument("--pipeline", choices=("legacy", "v2"), default="v2")
    parser.add_argument("--corpus-version", default=DEFAULT_CORPUS_VERSION)
    parser.add_argument("--tag", default=None, help="产物文件名标识（默认时间戳）")
    parser.add_argument("--persist", action="store_true", help="同时把汇总写入数据库")
    parser.add_argument(
        "--judge",
        type=int,
        default=0,
        help="LLM-as-judge：对前 N 条有据回答做忠实度/相关性评审（0=关闭，每题一次额外调用）",
    )
    parser.add_argument(
        "--provider-config-id",
        type=int,
        default=None,
        help="强制使用指定 llm_provider_configs.id 作为 LLM Provider"
             "（覆盖服务端兜底；QA 与 judge 同源）",
    )
    return parser


def _force_provider_factory(config_id: int):
    """构造替换版 select_provider：固定使用数据库中指定 Provider 配置。

    评测脚本运行于无登录用户的上下文，引擎默认走服务端 .env 兜底；
    此工厂允许评测临时改用某个用户配置的 Provider（如 opencode go / Mimo）。
    必须在 Flask app_context 内调用与执行。
    """
    from app import db
    from app.models.llm import LLMProviderConfig
    from app.services.llm.call_logging import observe_provider
    from app.services.llm.openai_compatible import OpenAICompatibleProvider
    from app.services.llm.secrets import decrypt_secret

    def select_forced(user_id: int | None = None, operation: str = "qa"):
        config = db.session.get(LLMProviderConfig, config_id)
        if config is None or not config.is_enabled:
            raise RuntimeError(f"provider_config_id={config_id} 不存在或未启用")
        provider = OpenAICompatibleProvider(
            provider_name=config.name,
            base_url=config.base_url,
            api_key=decrypt_secret(config.api_key_ciphertext),
            model=config.model,
            provider_config_id=config.id,
            user_id=user_id,
            operation=operation,
            max_tokens=config.max_tokens,
        )
        return observe_provider(provider, user_id=user_id, operation=operation)

    return select_forced


def load_review_status(path: Path) -> Dict[str, str]:
    """读取审批 CSV，返回 case_key -> review_status。"""
    status: Dict[str, str] = {}
    if not path.exists():
        return status
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("case_key") or "").strip()
            value = (row.get("review_status") or "").strip().lower()
            if key and value in {"approved", "rejected", "pending"}:
                status[key] = value
    return status


def filter_by_review(
    cases: Tuple[EvaluationCase, ...],
    status_map: Dict[str, str],
    *,
    include_pending: bool,
) -> Tuple[Tuple[EvaluationCase, ...], Dict[str, int]]:
    """按审批状态过滤；返回（入选用例, 各状态计数）。"""
    counts = {"approved": 0, "pending": 0, "rejected": 0, "unreviewed": 0}
    selected: List[EvaluationCase] = []
    for case in cases:
        state = status_map.get(case.case_key, "unreviewed")
        counts[state] += 1
        if state == "approved" or (
            include_pending and state in {"pending", "unreviewed"}
        ):
            selected.append(case)
    return tuple(selected), counts


def report_filename(tag: str, dataset: str) -> str:
    name = f"rag_report_{tag}_{dataset}.json"
    if not _REPORT_NAME.fullmatch(name):
        raise ValueError("tag 只能包含字母数字下划线连字符")
    return name


def _capture_wrapper(port, sink: Dict[int, Dict[str, Any]], progress_every: int = 10):
    """包装真实执行器：捕获逐题明细并打印进度。"""
    state = {"done": 0}

    def execute(case: EvaluationCase) -> EvaluationExecution:
        execution = port(case)
        candidates = list(execution.candidate_document_ids)[:5]
        sink[case.case_id] = {
            "candidate_top5": candidates,
            "answer_status": execution.answer_status,
            "retrieval_ms": execution.retrieval_ms,
            "rerank_ms": execution.rerank_ms,
            "evidence_token_count": execution.evidence_token_count,
        }
        state["done"] += 1
        if state["done"] % progress_every == 0:
            print(f"  ... 已完成 {state['done']} 题", flush=True)
        return execution

    return execute


def _capture_raw(raw_sink: Dict[int, Dict[str, Any]], case_id: int, result: Any) -> None:
    """on_result 钩子：留存回答原文与证据正文（供 LLM-as-judge 使用）。"""
    references = list(getattr(result.citations, "references", ()) or [])
    raw_sink[case_id] = {
        "answer": str(getattr(result, "answer", "") or ""),
        "model": getattr(result, "model_name", None),
        "references": [
            {
                "citation_id": getattr(ref, "citation_id", ""),
                "title": getattr(ref, "title", ""),
                "start_line": getattr(ref, "start_line", None),
                "end_line": getattr(ref, "end_line", None),
                "content": (getattr(ref, "content", "") or "")[:400],
            }
            for ref in references[:6]
        ],
    }


def run_dataset(
    *,
    dataset: str,
    cases: Tuple[EvaluationCase, ...],
    pipeline: str,
    corpus_version: str,
    tag: str,
    out_dir: Path,
    persist: bool,
    judge_limit: int = 0,
    provider_config_id: int | None = None,
) -> Dict[str, Any]:
    capture: Dict[int, Dict[str, Any]] = {}
    raw_sink: Dict[int, Dict[str, Any]] = {}
    port_builder = build_runtime_executor
    forced_selector = None
    if provider_config_id is not None:
        # 强制评测链路（QA 与 judge）使用指定 Provider 配置。
        import app.services.enhanced_rag_engine as _engine_module

        forced_selector = _force_provider_factory(provider_config_id)
        _engine_module.select_provider = forced_selector
        port_builder = build_runtime_executor
    port = port_builder(
        pipeline=pipeline,
        corpus_version=corpus_version,
        on_result=lambda case, result: _capture_raw(raw_sink, case.case_id, result)
        if judge_limit > 0
        else None,
    )
    evaluator = OfflineRagEvaluator(
        execute_case=_capture_wrapper(port, capture)
    )
    report = evaluator.evaluate(cases, pipeline=pipeline, corpus_version=corpus_version)

    summary_name = report_filename(tag, dataset)
    summary_path = BACKEND_ROOT / summary_name
    payload = report.to_report_dict()
    payload["report_file"] = summary_name
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    # LLM-as-judge：仅评审有据回答，逐题一次额外调用，成本由 --judge N 控制。
    verdicts_by_key: Dict[str, Dict[str, Any]] = {}
    if judge_limit > 0:
        from app.services.rag_core.answer_judge import judge_answer

        provider = (
            forced_selector(operation="judge")
            if forced_selector is not None
            else select_provider(operation="judge")
        )
        judged = 0
        for case in cases:
            if judged >= judge_limit:
                break
            info = raw_sink.get(case.case_id)
            if not info or not info.get("answer"):
                continue
            if capture.get(case.case_id, {}).get("answer_status") != "supported":
                continue
            print(f"  judging {case.case_key}", flush=True)
            verdicts_by_key[case.case_key] = judge_answer(
                case.query, info["answer"], info["references"], provider
            )
            judged += 1

    details_path = out_dir / f"eval_run_{tag}_{dataset}.jsonl"
    with details_path.open("w", encoding="utf-8", newline="\n") as handle:
        for case, outcome in zip(cases, report.outcomes):
            info = raw_sink.get(case.case_id) or {}
            row = {
                "case_key": case.case_key,
                "dataset": dataset,
                "query": case.query,
                "difficulty": case.difficulty,
                "expected_document_ids": list(case.expected_document_ids),
                "expected_status": case.expected_status,
                "retrieval_metrics": dict(outcome.retrieval_metrics),
                "evidence_metrics": dict(outcome.evidence_metrics),
                "citation_metrics": dict(outcome.citation_metrics),
                "failure_stage": outcome.failure_stage,
                "notes": list(outcome.notes),
                "execution": capture.get(case.case_id, {}),
                "answer_excerpt": info.get("answer", "")[:300] if judge_limit > 0 else None,
                "judge": verdicts_by_key.get(case.case_key),
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    run_id = None
    if persist:
        from app.services.rag_core.evaluation_persistence import (
            persist_evaluation_report,
        )

        try:
            run_id = persist_evaluation_report(report, report_path=summary_name)
        except Exception as exc:  # noqa: BLE001 - 输出前脱敏
            print(
                json.dumps({"persist_error": f"{type(exc).__name__}: {_sanitize(exc)}"}),
                file=sys.stderr,
            )

    return {
        "dataset": dataset,
        "cases": len(cases),
        "summary": summary_name,
        "details": str(details_path),
        "metrics": payload.get("metrics", {}),
        "run_id": run_id,
    }


def main() -> None:
    args = build_argument_parser().parse_args()
    tag = args.tag or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    selected_datasets = list(DATASETS) if args.dataset == "all" else [args.dataset]

    app = create_app()
    results = []
    with app.app_context():
        for dataset in selected_datasets:
            cases = DATASETS[dataset]
            review_path = DEFAULT_REVIEW_DIR / f"eval_review_{dataset}.csv"
            status_map = load_review_status(review_path)
            if status_map:
                cases, counts = filter_by_review(
                    cases, status_map, include_pending=args.include_pending
                )
                review_note = {"counts": counts, "file": str(review_path)}
            else:
                review_note = {
                    "counts": {"unreviewed": len(cases)},
                    "file": None,
                    "note": "未找到审批清单，全部参与",
                }
            if args.limit is not None and args.limit > 0:
                cases = cases[: args.limit]
            if not cases:
                print(
                    json.dumps(
                        {"dataset": dataset, "skipped": "过滤后无用例"},
                        ensure_ascii=False,
                    )
                )
                continue
            print(
                json.dumps(
                    {"dataset": dataset, "running_cases": len(cases), **review_note},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            results.append(
                run_dataset(
                    dataset=dataset,
                    cases=cases,
                    pipeline=args.pipeline,
                    corpus_version=args.corpus_version,
                    tag=tag,
                    out_dir=DEFAULT_DATA_DIR,
                    persist=args.persist,
                    judge_limit=args.judge,
                    provider_config_id=args.provider_config_id,
                )
            )
    print(json.dumps({"tag": tag, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
