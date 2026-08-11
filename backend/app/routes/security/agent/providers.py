"""A8 工作区 Agent Provider 策略端点（allowlist + 首选；不含密钥）。"""
from __future__ import annotations

from flask import jsonify
from flask_jwt_extended import jwt_required

from app import db
from app.models.security import Workspace
from app.services.security_agent.providers.policy import (
    KNOWN_PROVIDERS,
    ProviderPolicyError,
    WorkspaceProviderPolicy,
)

from .. import projects_bp
from ..common import (
    AuthorizationError,
    PROJECT_ROLES,
    _current_user_id,
    _json_object,
    require_workspace_role,
)

_policy = WorkspaceProviderPolicy()


@projects_bp.route("/workspaces/<int:workspace_id>/agent-provider-policy", methods=["GET"])
@jwt_required()
def get_agent_provider_policy(workspace_id: int):
    try:
        workspace = db.session.get(Workspace, workspace_id)
        if workspace is None:
            return jsonify({"error": "工作区不存在"}), 404
        require_workspace_role(workspace_id, _current_user_id(), PROJECT_ROLES)
        policy = _policy.get(workspace)
        policy["known_providers"] = list(KNOWN_PROVIDERS)
        return jsonify({"policy": policy})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/workspaces/<int:workspace_id>/agent-provider-policy", methods=["PUT"])
@jwt_required()
def update_agent_provider_policy(workspace_id: int):
    try:
        workspace = db.session.get(Workspace, workspace_id)
        if workspace is None:
            return jsonify({"error": "工作区不存在"}), 404
        require_workspace_role(workspace_id, _current_user_id(), PROJECT_ROLES)
        data = _json_object()
        allowlist = data.get("allowlist")
        preferred = data.get("preferred_provider")
        if allowlist is not None and not isinstance(allowlist, list):
            return jsonify({"error": "allowlist 必须是数组"}), 400
        if preferred is not None and not isinstance(preferred, str):
            return jsonify({"error": "preferred_provider 必须是字符串"}), 400
        updated = _policy.update(workspace, allowlist=allowlist, preferred_provider=preferred)
        return jsonify({"policy": _policy.get(updated)})
    except ProviderPolicyError as exc:
        return jsonify({"error": str(exc)}), 400
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
