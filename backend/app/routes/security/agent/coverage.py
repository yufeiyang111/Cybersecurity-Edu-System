"""Coverage and message endpoints for agent runs."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.agent_runtime import AgentMessage, AgentRun
from app.models.security import ScanTask
from app.services.scan_coverage.summary import coverage_summary, list_coverage_files

from .. import projects_bp
from ..common import (
    AuthorizationError,
    PROJECT_ROLES,
    READ_ROLES,
    _current_user_id,
    require_workspace_role,
)

AGENT_GOAL_MAX_CHARS = 4000


def _agent_run_or_404(run_id: int, allowed_roles: set[str] = READ_ROLES) -> AgentRun | None:
    run = db.session.get(AgentRun, run_id)
    if run is None:
        return None
    require_workspace_role(run.workspace_id, _current_user_id(), allowed_roles)
    return run


def _scan_task_for_run(run: AgentRun) -> ScanTask | None:
    return (
        ScanTask.query.filter_by(snapshot_id=run.snapshot_id)
        .order_by(ScanTask.id.desc())
        .first()
    )


@projects_bp.route("/agent-runs/<int:run_id>/coverage", methods=["GET"])
@jwt_required()
def get_agent_run_coverage(run_id: int):
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        task = _scan_task_for_run(run)
        if task is None:
            return jsonify({"coverage": None, "files": [], "pagination": {"total": 0, "limit": 0, "offset": 0}})
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        kind = request.args.get("kind")
        if not 1 <= limit <= 200 or offset < 0:
            return jsonify({"error": "limit 必须在 1 至 200 之间，offset 不能小于 0"}), 400
        files, total = list_coverage_files(task, kind=kind, limit=limit, offset=offset)
        return jsonify(
            {
                "coverage": coverage_summary(task),
                "files": files,
                "pagination": {"total": total, "limit": limit, "offset": offset},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
