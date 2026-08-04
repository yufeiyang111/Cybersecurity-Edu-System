"""Security project collection endpoints."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.security import SecurityProject
from app.services.security_workbench import build_workspace_dashboard

from . import projects_bp
from .common import AuthorizationError, READ_ROLES, _current_user_id, get_or_create_personal_workspace, require_workspace_role

@projects_bp.route("/projects", methods=["POST"])
@jwt_required()
def create_project():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 200:
        return jsonify({"error": "项目名称长度必须在 1 到 200 个字符之间"}), 400

    try:
        user_id = _current_user_id()
        workspace = get_or_create_personal_workspace(user_id)
        require_workspace_role(workspace.id, user_id, {"owner", "security_admin", "analyst", "developer"})
        project = SecurityProject(workspace_id=workspace.id, name=name, created_by=user_id)
        db.session.add(project)
        db.session.commit()
        return jsonify({"project": project.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception:
        db.session.rollback()
        return jsonify({"error": "创建项目失败"}), 409


@projects_bp.route("/projects", methods=["GET"])
@jwt_required()
def list_projects():
    try:
        workspace = get_or_create_personal_workspace(_current_user_id())
        require_workspace_role(workspace.id, _current_user_id(), READ_ROLES)
        dashboard = build_workspace_dashboard(workspace.id)
        return jsonify({"items": dashboard["projects"]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
