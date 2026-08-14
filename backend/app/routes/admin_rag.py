# -*- coding: utf-8 -*-
"""RAG 管理诊断接口：仅返回脱敏 trace 与受控评测运行摘要。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from app import db

from app.models.qa import RagEvaluationResult, RagEvaluationRun, RagRetrievalTrace
from app.services.rag_core.admin_trace_summary import build_admin_trace_stage_summary

admin_rag_bp = Blueprint("admin_rag", __name__)

_MAX_PAGE_SIZE = 100


def _require_admin() -> bool:
    """仅接受 JWT 内明确声明的管理员角色。"""
    return get_jwt().get("role") == "admin"


def _page_arguments() -> tuple[int, int]:
    """限制管理列表分页，避免无界读取。"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return max(1, page or 1), min(_MAX_PAGE_SIZE, max(1, per_page or 20))


def _serialize_trace(trace: RagRetrievalTrace) -> dict:
    """二次脱敏已有 trace，防御历史脏数据或手工写入。"""
    stage_summary = build_admin_trace_stage_summary(trace.stage_summary_json)
    warnings = [
        warning
        for warning in (trace.warnings_json or [])
        if isinstance(warning, str) and warning.strip()
    ]

    return {
        "id": trace.id,
        "pipeline_version_id": trace.pipeline_version_id,
        "stage_summary": stage_summary,
        "warnings": warnings,
        "retrieval_ms": trace.retrieval_ms,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }


def _serialize_evaluation_run(run: RagEvaluationRun) -> dict:
    """评测运行摘要不返回内部报告路径。"""
    return {
        "id": run.id,
        "pipeline_version_id": run.pipeline_version_id,
        "corpus_version": run.corpus_version,
        "status": run.status,
        "metrics": run.metrics_json or {},
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@admin_rag_bp.route("/rag/traces/<int:trace_id>", methods=["GET"])
@jwt_required()
def get_rag_trace(trace_id: int):
    """管理员读取单条脱敏检索 trace。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    trace = db.session.get(RagRetrievalTrace, trace_id)
    if trace is None:
        return jsonify({"error": "检索追踪记录不存在"}), 404
    return jsonify({"trace": _serialize_trace(trace)}), 200


@admin_rag_bp.route("/rag/evaluation-runs", methods=["GET"])
@jwt_required()
def list_evaluation_runs():
    """管理员分页查看评测运行摘要。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    page, per_page = _page_arguments()
    pagination = (
        RagEvaluationRun.query
        .order_by(RagEvaluationRun.started_at.desc(), RagEvaluationRun.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "runs": [_serialize_evaluation_run(run) for run in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@admin_rag_bp.route("/rag/evaluation-runs/<int:run_id>", methods=["GET"])
@jwt_required()
def get_evaluation_run(run_id: int):
    """管理员查看评测运行和其受控结果摘要。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    run = db.session.get(RagEvaluationRun, run_id)
    if run is None:
        return jsonify({"error": "评测运行不存在"}), 404

    page, per_page = _page_arguments()
    pagination = (
        RagEvaluationResult.query
        .filter_by(run_id=run_id)
        .order_by(RagEvaluationResult.id.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    results = [
        {
            "id": result.id,
            "case_id": result.case_id,
            "retrieval_metrics": result.retrieval_metrics_json or {},
            "citation_metrics": result.citation_metrics_json or {},
            "answer_metrics": result.answer_metrics_json or {},
            "failure_stage": result.failure_stage,
            "created_at": result.created_at.isoformat() if result.created_at else None,
        }
        for result in pagination.items
    ]
    return jsonify({
        "run": _serialize_evaluation_run(run),
        "results": results,
        "result_page": {
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
        },
    }), 200