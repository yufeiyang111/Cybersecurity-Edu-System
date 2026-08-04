"""项目级扫描排除规则管理端点（gitignore 风格）。"""
from __future__ import annotations

from flask import current_app, jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.security import ProjectExclusionRule, SecurityProject
from app.services.exclusion_service import (
    ExclusionRuleError,
    add_exclusion_rule,
    delete_exclusion_rule,
    list_exclusion_rules,
    replace_exclusion_rules,
)

from . import projects_bp
from .common import (
    AuthorizationError,
    PROJECT_ROLES,
    READ_ROLES,
    _current_user_id,
    require_workspace_role,
)


def _project_or_404(project_id: int) -> SecurityProject:
    project = db.session.get(SecurityProject, project_id)
    if project is None:
        raise LookupError
    return project


@projects_bp.route("/projects/<int:project_id>/exclusions", methods=["GET"])
@jwt_required()
def list_exclusions(project_id: int):
    """返回项目的排除规则列表（按匹配顺序）。"""
    try:
        project = _project_or_404(project_id)
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, READ_ROLES)
        rules = list_exclusion_rules(project.id)
        return jsonify({"items": [rule.to_dict() for rule in rules]})
    except LookupError:
        return jsonify({"error": "项目不存在"}), 404
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/projects/<int:project_id>/exclusions", methods=["PUT"])
@jwt_required()
def replace_exclusions(project_id: int):
    """整体替换项目排除规则（gitignore 文件式编辑）。"""
    try:
        project = _project_or_404(project_id)
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        data = request.get_json(silent=True) or {}
        patterns = data.get("patterns", [])
        if not isinstance(patterns, list) or any(not isinstance(item, str) for item in patterns):
            return jsonify({"error": "patterns 必须是字符串列表"}), 400
        rules = replace_exclusion_rules(project, user_id, patterns)
        return jsonify({"items": [rule.to_dict() for rule in rules]}), 200
    except LookupError:
        return jsonify({"error": "项目不存在"}), 404
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/projects/<int:project_id>/exclusions/items", methods=["POST"])
@jwt_required()
def create_exclusion(project_id: int):
    """追加一条排除规则。"""
    try:
        project = _project_or_404(project_id)
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        data = request.get_json(silent=True) or {}
        pattern = str(data.get("pattern", "")).strip()
        if not pattern:
            return jsonify({"error": "请提供规则内容"}), 400
        rule = add_exclusion_rule(project, user_id, pattern)
        return jsonify({"item": rule.to_dict()}), 201
    except LookupError:
        return jsonify({"error": "项目不存在"}), 404
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ExclusionRuleError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/projects/<int:project_id>/exclusions/items/<int:rule_id>", methods=["DELETE"])
@jwt_required()
def remove_exclusion(project_id: int, rule_id: int):
    """删除一条排除规则。"""
    try:
        project = _project_or_404(project_id)
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        rule = db.session.get(ProjectExclusionRule, rule_id)
        if rule is None or rule.project_id != project.id:
            return jsonify({"error": "规则不存在"}), 404
        delete_exclusion_rule(rule, user_id)
        return jsonify({}), 204
    except LookupError:
        return jsonify({"error": "项目不存在"}), 404
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
