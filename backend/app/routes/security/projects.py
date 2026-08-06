"""Security project collection endpoints."""
from __future__ import annotations

from flask import current_app, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.security import AuditEvent, SecurityProject
from app.services.project_lifecycle import ProjectLifecycleError, delete_project
from app.services.security_workbench import build_workspace_dashboard

from . import projects_bp
from .common import AuthorizationError, PROJECT_ROLES, READ_ROLES, _current_user_id, get_or_create_personal_workspace, require_workspace_role

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


def _project_or_404_checked(project_id: int) -> SecurityProject | None:
    """按写角色获取项目并校验归属。"""
    project = db.session.get(SecurityProject, project_id)
    if project is None:
        return None
    user_id = _current_user_id()
    require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
    return project


@projects_bp.route("/projects/<int:project_id>", methods=["PUT"])
@jwt_required()
def update_project(project_id: int):
    """更新项目名称、描述与默认分支。"""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip() if "name" in data else None
    if name is not None and (not name or len(name) > 200):
        return jsonify({"error": "项目名称长度必须在 1 到 200 个字符之间"}), 400
    if name is None and "description" not in data and "default_branch" not in data:
        return jsonify({"error": "没有需要更新的字段"}), 400
    description = data.get("description")
    if description is not None and (not isinstance(description, str) or len(description) > 2000):
        return jsonify({"error": "项目描述不能超过 2000 个字符"}), 400
    default_branch = data.get("default_branch")
    if default_branch is not None and (not isinstance(default_branch, str) or len(default_branch) > 255):
        return jsonify({"error": "默认分支长度不能超过 255 个字符"}), 400

    try:
        project = _project_or_404_checked(project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        changes = {}
        if name is not None and name != project.name:
            project.name = name
            changes["name"] = True
        if description is not None and description != project.description:
            project.description = description or None
            changes["description"] = True
        if default_branch is not None and default_branch != project.default_branch:
            project.default_branch = default_branch or None
            changes["default_branch"] = True
        if changes:
            db.session.add(
                AuditEvent(
                    workspace_id=project.workspace_id,
                    actor_id=user_id,
                    action="project.updated",
                    target_type="security_project",
                    target_id=project.id,
                    metadata_json={"fields": list(changes.keys())},
                )
            )
            db.session.commit()
        return jsonify({"project": project.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "项目名称已存在"}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("更新项目失败 (project_id=%s)", project_id)
        return jsonify({"error": "更新项目失败"}), 500


@projects_bp.route("/projects/<int:project_id>", methods=["DELETE"])
@jwt_required()
def delete_project_endpoint(project_id: int):
    """删除项目：拒绝存在 Agent 运行或会话记录的项目。"""
    try:
        project = _project_or_404_checked(project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        workspace_root = str(current_app.config["SECURITY_WORKSPACE_ROOT"])
        delete_project(project, _current_user_id(), workspace_root)
        return jsonify({"deleted": True})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ProjectLifecycleError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("删除项目失败 (project_id=%s)", project_id)
        return jsonify({"error": "删除项目失败"}), 500
