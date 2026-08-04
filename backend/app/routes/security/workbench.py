"""安全工作台总览端点。"""
from __future__ import annotations

from flask import jsonify
from flask_jwt_extended import jwt_required

from app.services.security_workbench import build_workspace_dashboard

from . import projects_bp
from .common import (
    AuthorizationError,
    READ_ROLES,
    _current_user_id,
    get_or_create_personal_workspace,
    require_workspace_role,
)


@projects_bp.route("/workbench/overview", methods=["GET"])
@jwt_required()
def workbench_overview():
    try:
        workspace = get_or_create_personal_workspace(_current_user_id())
        require_workspace_role(workspace.id, _current_user_id(), READ_ROLES)
        dashboard = build_workspace_dashboard(workspace.id)
        return jsonify(
            {
                "total_projects": dashboard["total_projects"],
                "total_scans": dashboard["total_scans"],
                "totals": dashboard["totals"],
                "recent_scans": dashboard["recent_scans"],
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403