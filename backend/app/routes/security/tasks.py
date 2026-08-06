"""任务、依赖、发现项和任务控制端点。"""
from __future__ import annotations

from flask import current_app, jsonify, request
from app.services.rate_limit import rate_limit
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app import db
from app.models.security import (
    ProjectSnapshot,
    RemediationSuggestion,
    ScanTask,
    SnapshotDependency,
)
from app.services.scan_task_lifecycle import (
    ScanTaskStateError,
    cancel_scan_task,
    mark_dispatch_failed,
    prepare_scan_task_retry,
)
from app.services.task_dispatcher import get_scan_task_dispatcher
from app.services.project_lifecycle import ProjectLifecycleError, delete_scan_task

from . import projects_bp
from .common import (
    AuthorizationError,
    PROJECT_ROLES,
    _current_user_id,
    _list_params,
    _pagination_payload,
    _project_or_404,
    _task_or_404,
)


@projects_bp.route("/projects/<int:project_id>/dependencies", methods=["GET"])
@jwt_required()
def list_project_dependencies(project_id: int):
    try:
        project = _project_or_404(project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        snapshot_id = request.args.get("snapshot_id", type=int)
        query = SnapshotDependency.query.join(ProjectSnapshot).filter(ProjectSnapshot.project_id == project.id)
        if snapshot_id is not None:
            query = query.filter(SnapshotDependency.snapshot_id == snapshot_id)
        dependencies = query.order_by(
            SnapshotDependency.ecosystem,
            SnapshotDependency.package_name,
            SnapshotDependency.version,
        ).all()
        total = len(dependencies)
        limit, offset = _list_params()
        page = dependencies[offset : offset + limit]
        return jsonify(
            {
                "items": [dependency.to_dict() for dependency in page],
                "pagination": _pagination_payload(total=total, limit=limit, offset=offset),
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/projects/<int:project_id>/tasks", methods=["GET"])
@jwt_required()
def list_project_tasks(project_id: int):
    try:
        project = _project_or_404(project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        tasks = (
            ScanTask.query.join(ProjectSnapshot)
            .filter(ProjectSnapshot.project_id == project.id)
            .order_by(ScanTask.created_at.desc(), ScanTask.id.desc())
            .all()
        )
        return jsonify({"items": [task.to_dict() for task in tasks]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/tasks/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id: int):
    try:
        task = _task_or_404(task_id)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        return jsonify({"task": task.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/tasks/<int:task_id>/findings", methods=["GET"])
@jwt_required()
def get_task_findings(task_id: int):
    try:
        task = _task_or_404(task_id)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        from app.services.risk_scoring import policy_from_config, score_finding

        policy = policy_from_config(current_app.config)
        items = []
        for finding in task.findings:
            payload = finding.to_dict(include_evidence=True)
            payload["risk"] = score_finding(finding, policy=policy).to_dict()
            items.append(payload)
        if request.args.get("sort", "") == "risk":
            priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            items.sort(
                key=lambda item: (
                    priority_order.get(item["risk"]["priority"], 0),
                    item["risk"]["score"],
                    -(item.get("id") or 0),
                ),
                reverse=True,
            )
        else:
            items.sort(key=lambda item: item.get("id") or 0)

        total = len(items)
        limit, offset = _list_params()
        page = items[offset : offset + limit]

        suggestion_counts, suggestion_reviewed = _suggestion_aggregates(
            [finding.id for finding in task.findings]
        )
        for item in items:
            item["suggestion_count"] = suggestion_counts.get(item["id"], 0)

        scores = [
            item["risk"].get("score")
            for item in items
            if isinstance(item["risk"].get("score"), (int, float))
        ]
        return jsonify(
            {
                "items": page,
                "pagination": _pagination_payload(total=total, limit=limit, offset=offset),
                "stats": {
                    "total": total,
                    "high_count": sum(
                        1 for item in items if item.get("severity") in {"critical", "high"}
                    ),
                    "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
                    "suggestion_total": sum(suggestion_counts.values()),
                    "suggestion_reviewed": suggestion_reviewed,
                },
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


def _suggestion_aggregates(finding_ids: list[int]) -> tuple[dict[int, int], int]:
    """按 finding 聚合建议数，并统计已审核（非 pending）数量。"""
    if not finding_ids:
        return {}, 0
    count_rows = (
        db.session.query(RemediationSuggestion.finding_id, func.count(RemediationSuggestion.id))
        .filter(RemediationSuggestion.finding_id.in_(finding_ids))
        .group_by(RemediationSuggestion.finding_id)
        .all()
    )
    counts = {finding_id: count for finding_id, count in count_rows}
    reviewed = (
        db.session.query(func.count(RemediationSuggestion.id))
        .filter(
            RemediationSuggestion.finding_id.in_(finding_ids),
            RemediationSuggestion.review_state.in_(["accepted", "rejected", "needs_revision"]),
        )
        .scalar()
        or 0
    )
    return counts, reviewed


@projects_bp.route("/tasks/<int:task_id>/cancel", methods=["POST"])
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def cancel_task(task_id: int):
    try:
        task = _task_or_404(task_id, PROJECT_ROLES)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        cancel_scan_task(task, actor_id=_current_user_id())
        return jsonify({"task": task.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ScanTaskStateError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409


@projects_bp.route("/tasks/<int:task_id>/retry", methods=["POST"])
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def retry_task(task_id: int):
    try:
        task = _task_or_404(task_id, PROJECT_ROLES)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        task = prepare_scan_task_retry(
            task,
            actor_id=_current_user_id(),
            max_retries=int(current_app.config.get("SCAN_TASK_MAX_RETRIES", 3)),
        )
        try:
            get_scan_task_dispatcher().enqueue(task.id, task.dispatch_key)
        except Exception as exc:
            db.session.rollback()
            failed_task = mark_dispatch_failed(task.id)
            current_app.logger.exception("扫描任务重试派发失败 (task_id=%s)", task_id)
            return jsonify({"error": "重新派发扫描任务失败", "task": failed_task.to_dict() if failed_task else None}), 502
        refreshed = db.session.get(ScanTask, task.id) or task
        return jsonify({"task": refreshed.to_dict()}), 202
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ScanTaskStateError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409


@projects_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id: int):
    """删除已结束的扫描任务及其发现项、证据、修复建议和覆盖率单据。"""
    try:
        task = _task_or_404(task_id, PROJECT_ROLES)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        delete_scan_task(task, _current_user_id())
        return jsonify({"deleted": True})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ProjectLifecycleError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("删除扫描任务失败 (task_id=%s)", task_id)
        return jsonify({"error": "删除扫描任务失败"}), 500
