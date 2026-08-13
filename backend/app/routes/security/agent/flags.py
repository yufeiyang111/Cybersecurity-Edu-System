# -*- coding: utf-8 -*-
"""Agent v2 Feature Flag 管理端点（S-02/S-06 灰度与回滚演练）。

- GET 返回 workspace 解析后的最终 flag（全局 ∧ 降级覆盖）；
- PATCH 只接受布尔 false 的降级覆盖（或 null 清除）——workspace 不能
  自行开启全局关闭的 v2 能力（deny by default）。
"""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.security import Workspace
from app.services.security_agent.feature_flags import (
    AGENT_FEATURE_FLAG_KEYS,
    AgentFeatureFlags,
)

from .. import projects_bp
from ..common import (
    AuthorizationError,
    KNOWLEDGE_ADMIN_ROLES,
    _current_user_id,
    _json_object,
    require_workspace_role,
)

WORKSPACE_ADMIN_ROLES = KNOWLEDGE_ADMIN_ROLES


def _workspace_or_404(workspace_id: int) -> Workspace | None:
    workspace = db.session.get(Workspace, workspace_id)
    if workspace is None:
        return None
    require_workspace_role(workspace_id, _current_user_id(), WORKSPACE_ADMIN_ROLES)
    return workspace


@projects_bp.route("/workspaces/<int:workspace_id>/agent-feature-flags", methods=["GET"])
@jwt_required()
def get_workspace_agent_feature_flags(workspace_id: int):
    try:
        workspace = _workspace_or_404(workspace_id)
        if workspace is None:
            return jsonify({"error": "工作区不存在"}), 404
        flags = AgentFeatureFlags().for_workspace(workspace_id)
        return jsonify(
            {
                "resolved": flags.as_dict(),
                "overrides": workspace.agent_feature_flags or {},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route(
    "/workspaces/<int:workspace_id>/agent-feature-flags", methods=["PATCH"]
)
@jwt_required()
def update_workspace_agent_feature_flags(workspace_id: int):
    try:
        workspace = _workspace_or_404(workspace_id)
        if workspace is None:
            return jsonify({"error": "工作区不存在"}), 404
        data = _json_object()
        overrides = data.get("overrides")
        if not isinstance(overrides, dict):
            return jsonify({"error": "overrides 必须是对象"}), 400
        unknown = [key for key in overrides if key not in AGENT_FEATURE_FLAG_KEYS]
        if unknown:
            return (
                jsonify(
                    {
                        "error": f"未知 flag：{', '.join(sorted(unknown))}；只允许 "
                        f"{'、'.join(AGENT_FEATURE_FLAG_KEYS)}"
                    }
                ),
                400,
            )
        for key, value in overrides.items():
            if value is not None and value is not False:
                return (
                    jsonify(
                        {
                            "error": f"{key} 只允许 false（降级）或 null（清除覆盖），"
                            "workspace 不能自行开启全局关闭的能力"
                        }
                    ),
                    400,
                )
        current = dict(workspace.agent_feature_flags or {})
        for key, value in overrides.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = False
        workspace.agent_feature_flags = current or None
        db.session.commit()
        AgentFeatureFlags().invalidate(workspace_id)
        return jsonify(
            {
                "resolved": AgentFeatureFlags().for_workspace(workspace_id).as_dict(),
                "overrides": workspace.agent_feature_flags or {},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
