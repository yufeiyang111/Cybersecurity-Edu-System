# -*- coding: utf-8 -*-
"""企业 RAG 评测安全摘要的数据库持久化。"""
from __future__ import annotations

from .evaluation_contracts import EvaluationReport


def persist_evaluation_report(report: EvaluationReport, *, report_path: str | None = None) -> int:
    """仅保存指标摘要、版本和受控报告文件名。"""
    from app import db
    from app.models.qa import RagEvaluationResult, RagEvaluationRun, RagPipelineVersion

    safe_path = _safe_report_path(report_path)
    version = None
    if len(report.pipeline_version_keys) == 1:
        version = RagPipelineVersion.query.filter_by(version_key=report.pipeline_version_keys[0]).first()
    run = RagEvaluationRun(
        pipeline_version_id=version.id if version else None,
        corpus_version=report.corpus_version,
        status="completed" if not any(outcome.failure_stage == "execution" for outcome in report.outcomes) else "completed_with_failures",
        metrics_json=report.to_report_dict()["metrics"],
        report_path=safe_path,
        started_at=report.started_at,
        finished_at=report.finished_at,
    )
    db.session.add(run)
    db.session.flush()
    for outcome in report.outcomes:
        storage = outcome.to_storage_dict()
        db.session.add(RagEvaluationResult(
            run_id=run.id,
            case_id=outcome.case_id,
            retrieval_metrics_json=storage["retrieval_metrics"],
            citation_metrics_json=storage["citation_metrics"],
            answer_metrics_json=storage["answer_metrics"],
            failure_stage=storage["failure_stage"],
            notes=storage["notes"],
        ))
    db.session.commit()
    return int(run.id)


def _safe_report_path(report_path: str | None) -> str | None:
    if report_path is None:
        return None
    normalized = report_path.replace("\\", "/").strip()
    if not normalized or "/" in normalized or ".." in normalized:
        raise ValueError("report_path must be a report file name")
    if not normalized.startswith("rag_report_") or not normalized.endswith(".json"):
        raise ValueError("report_path must be a rag_report_*.json file name")
    return normalized


__all__ = ["persist_evaluation_report"]