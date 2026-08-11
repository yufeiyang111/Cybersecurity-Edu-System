"""A9 Agent 可观测性路由：工作区运维概览与运行列表（只读，服务端分页）。"""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.models.security import Workspace
from app.services.agent_observability.operations import (
    observability_overview,
    observability_runs,
)

from .. import projects_bp
from ..common import (
    AuthorizationError,
    READ_ROLES,
    _current_user_id,
    require_workspace_role,
)


@projects_bp.route("/agent/observability/overview", methods=["GET"])
@jwt_required()
def agent_observability_overview():
    try:
        workspace_id = request.args.get("workspace_id", type=int)
        if not workspace_id:
            return jsonify({"error": "缺少 workspace_id 参数"}), 400
        require_workspace_role(workspace_id, _current_user_id(), READ_ROLES)
        days = request.args.get("days", 7, type=int)
        if not 1 <= days <= 90:
            return jsonify({"error": "days 必须在 1 至 90 之间"}), 400
        return jsonify({"overview": observability_overview(workspace_id=workspace_id, days=days)})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent/observability/runs", methods=["GET"])
@jwt_required()
def agent_observability_runs():
    try:
        workspace_id = request.args.get("workspace_id", type=int)
        if not workspace_id:
            return jsonify({"error": "缺少 workspace_id 参数"}), 400
        require_workspace_role(workspace_id, _current_user_id(), READ_ROLES)
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        status_filter = request.args.get("status")
        mode_filter = request.args.get("mode")
        if page < 1 or not 1 <= page_size <= 100:
            return jsonify({"error": "page 必须大于 0，page_size 必须在 1 至 100 之间"}), 400
        items, total = observability_runs(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            status=status_filter,
            mode=mode_filter,
        )
        return jsonify(
            {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
