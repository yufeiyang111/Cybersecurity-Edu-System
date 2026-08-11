"""AgentApproval endpoints: workspace queue (paged), run approvals, resolve."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.agent_approval import ApprovalStatus
from app.models.agent_runtime import AgentRun
from app.models.security import Workspace, WorkspaceMember
from app.services.security_agent.approval_service import (
    ApprovalConflictError,
    ApprovalError,
    ApprovalExpiredError,
    ApprovalService,
)
from app.services.security_agent.state_machine import AgentStateError

from .. import projects_bp
from ..common import (
    AuthorizationError,
    PROJECT_ROLES,
    READ_ROLES,
    _current_user_id,
    _json_object,
    require_workspace_role,
)

_service = ApprovalService()


def _current_role(workspace_id: int) -> str | None:
    member = (
        WorkspaceMember.query.filter_by(
            workspace_id=workspace_id, user_id=_current_user_id()
        ).first()
    )
    return member.role if member is not None else None


@projects_bp.route("/agent-approvals", methods=["GET"])
@jwt_required()
def list_agent_approvals():
    """工作区审批队列（服务端分页；pending 优先展示）。"""
    try:
        workspace_id = request.args.get("workspace_id", type=int)
        if not workspace_id:
            return jsonify({"error": "缺少 workspace_id 参数"}), 400
        workspace = db.session.get(Workspace, workspace_id)
        if workspace is None:
            return jsonify({"error": "工作区不存在"}), 404
        require_workspace_role(workspace_id, _current_user_id(), READ_ROLES)
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        status_filter = request.args.get("status")
        if page < 1 or not 1 <= page_size <= 100:
            return jsonify({"error": "page 必须大于 0，page_size 必须在 1 至 100 之间"}), 400
        rows, total = _service.list_for_workspace(
            workspace_id, page=page, page_size=page_size, status=status_filter
        )
        role = _current_role(workspace_id)
        items = []
        for approval in rows:
            item = approval.to_dict()
            run = db.session.get(AgentRun, approval.run_id)
            item["run_goal"] = run.goal_text[:100] if run else ""
            item["can_resolve"] = role in {"owner", "admin"}
            items.append(item)
        return jsonify(
            {"items": items, "total": total, "page": page, "page_size": page_size}
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/approvals", methods=["GET"])
@jwt_required()
def list_agent_run_approvals(run_id: int):
    try:
        run = db.session.get(AgentRun, run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        require_workspace_role(run.workspace_id, _current_user_id(), READ_ROLES)
        rows = _service.list_for_run(run.id)
        return jsonify({"items": [approval.to_dict() for approval in rows]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route(
    "/agent-runs/<int:run_id>/approvals/<int:approval_id>/resolve", methods=["POST"]
)
@jwt_required()
def resolve_agent_approval(run_id: int, approval_id: int):
    """Owner/Security Admin 批准或拒绝（单次使用，防重放 digest，可过期）。"""
    try:
        run = db.session.get(AgentRun, run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        require_workspace_role(run.workspace_id, _current_user_id(), PROJECT_ROLES)
        data = _json_object()
        decision = data.get("decision")
        comment = data.get("comment") or ""
        if decision not in {"approved", "rejected"}:
            return jsonify({"error": "decision 必须是 approved 或 rejected"}), 400
        if not isinstance(comment, str) or len(comment) > 1000:
            return jsonify({"error": "comment 不能超过 1000 字符"}), 400

        approval = _service.resolve(
            run,
            approval_id,
            decision=decision,
            comment=comment,
            resolver_id=_current_user_id(),
            resolver_role=_current_role(run.workspace_id),
        )
        return jsonify({"approval": approval.to_dict()})
    except ApprovalExpiredError as exc:
        return jsonify({"error": str(exc)}), 409
    except ApprovalConflictError as exc:
        return jsonify({"error": str(exc)}), 409
    except ApprovalError as exc:
        return jsonify({"error": str(exc)}), 403
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except AgentStateError as exc:
        return jsonify({"error": str(exc)}), 409
