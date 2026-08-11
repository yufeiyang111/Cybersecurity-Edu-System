"""AgentRun lifecycle endpoints: create, detail, pause, resume, cancel, events."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.agent_runtime import AgentDecisionRecord, AgentPlan, AgentRun
from app.models.security import ProjectSnapshot, SecurityProject
from app.services.security_agent.contracts import AGENT_RUN_MODES
from app.services.security_agent.cost_service import run_costs
from app.services.security_agent.service import AgentRunService
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

AGENT_GOAL_MAX_CHARS = 4000

_service = AgentRunService()


def _agent_run_or_404(run_id: int, allowed_roles: set[str] = READ_ROLES) -> AgentRun | None:
    run = db.session.get(AgentRun, run_id)
    if run is None:
        return None
    require_workspace_role(run.workspace_id, _current_user_id(), allowed_roles)
    return run


@projects_bp.route("/projects/<int:project_id>/agent-runs", methods=["POST"])
@jwt_required()
def create_agent_run(project_id: int):
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)

        data = _json_object()
        goal_text = data.get("goal_text")
        if not isinstance(goal_text, str) or not goal_text.strip():
            return jsonify({"error": "请描述本次 Agent 审计目标"}), 400
        goal_text = goal_text.strip()
        if len(goal_text) > AGENT_GOAL_MAX_CHARS:
            return jsonify({"error": f"审计目标长度不能超过 {AGENT_GOAL_MAX_CHARS} 个字符"}), 400

        mode = str(data.get("mode", "baseline")).strip().lower()
        if mode not in AGENT_RUN_MODES:
            return jsonify({"error": "mode 必须是 baseline、hybrid 或 deep_audit"}), 400

        budget = data.get("budget")
        if budget is not None and not isinstance(budget, dict):
            return jsonify({"error": "budget 必须是对象"}), 400

        snapshot = (
            ProjectSnapshot.query.filter_by(project_id=project.id)
            .order_by(ProjectSnapshot.id.desc())
            .first()
        )
        if snapshot is None:
            return jsonify({"error": "项目还没有可用的快照，请先上传 ZIP 或拉取 GitHub 项目"}), 409

        run = _service.create_run(
            project=project,
            snapshot=snapshot,
            user_id=user_id,
            goal_text=goal_text,
            mode=mode,
            budget=budget or {},
        )
        return jsonify({"run": run.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-runs/<int:run_id>", methods=["GET"])
@jwt_required()
def get_agent_run(run_id: int):
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        return jsonify(_service.get_run_payload(run))
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/pause", methods=["POST"])
@jwt_required()
def pause_agent_run(run_id: int):
    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        _service.pause_run(run, _current_user_id())
        return jsonify({"run": run.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except AgentStateError as exc:
        return jsonify({"error": str(exc)}), 409


@projects_bp.route("/agent-runs/<int:run_id>/resume", methods=["POST"])
@jwt_required()
def resume_agent_run(run_id: int):
    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        _service.resume_run(run, _current_user_id())
        return jsonify({"run": run.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except AgentStateError as exc:
        return jsonify({"error": str(exc)}), 409


@projects_bp.route("/agent-runs/<int:run_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_agent_run(run_id: int):
    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        _service.cancel_run(run, _current_user_id())
        return jsonify({"run": run.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except AgentStateError as exc:
        return jsonify({"error": str(exc)}), 409


@projects_bp.route("/agent-runs/<int:run_id>/events", methods=["GET"])
@jwt_required()
def list_agent_run_events(run_id: int):
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        limit = request.args.get("limit", 100, type=int)
        after = request.args.get("after", 0, type=int)
        if not 1 <= limit <= 200 or after < 0:
            return jsonify({"error": "limit 必须在 1 至 200 之间，after 不能小于 0"}), 400
        events = _service.list_events(run.id, after_sequence=after, limit=limit)
        return jsonify(
            {
                "items": [event.to_dict() for event in events],
                "last_sequence": run.last_event_sequence,
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-runs/<int:run_id>/costs", methods=["GET"])
@jwt_required()
def get_agent_run_costs(run_id: int):
    """Per-run LLM invocation list and cost summary (provider_reported/estimated/unknown)."""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        return jsonify(run_costs(run))
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/plans", methods=["GET"])
@jwt_required()
def list_agent_run_plans(run_id: int):
    """按版本列出计划 DAG（A5 计划版本选择器）。"""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        plans = (
            AgentPlan.query.filter_by(run_id=run.id)
            .order_by(AgentPlan.plan_version.asc())
            .all()
        )
        return jsonify({"items": [plan.to_dict() for plan in plans]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/decisions", methods=["GET"])
@jwt_required()
def list_agent_run_decisions(run_id: int):
    """重规划决策记录（A5 决策时间线）。"""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        records = (
            AgentDecisionRecord.query.filter_by(run_id=run.id)
            .order_by(AgentDecisionRecord.id.asc())
            .all()
        )
        return jsonify({"items": [record.to_dict() for record in records]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/messages", methods=["POST"])
@jwt_required()
def post_agent_run_message(run_id: int):
    """用户对运行中的 Agent 追加方向（A5）：创建新计划版本继续执行。

    幂等：相同 client_message_id 重试返回既有消息与计划版本（replayed=True）。
    Run 已终态时返回 409，由会话级接口创建新的 Turn + Run。
    """
    from app.models.conversation import AgentConversationMessage
    from app.services.security_agent.conversation_service import (
        ConversationError,
        ConversationService,
    )

    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404

        data = _json_object()
        content = data.get("content")
        client_message_id = data.get("client_message_id")
        if not isinstance(content, str) or not content.strip():
            return jsonify({"error": "消息内容不能为空"}), 400
        if not isinstance(client_message_id, str) or not client_message_id.strip():
            return jsonify({"error": "缺少 client_message_id（用于防重复提交）"}), 400

        from app.models.agent_runtime import AgentRunStatus

        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        terminal_statuses = {
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
        if status in terminal_statuses:
            return (
                jsonify(
                    {
                        "error": "任务已结束，追加方向请通过会话消息创建新的执行",
                        "terminal": True,
                    }
                ),
                409,
            )
        replanable_statuses = {
            AgentRunStatus.QUEUED.value,
            AgentRunStatus.PREPARING.value,
            AgentRunStatus.MAPPING_REPOSITORY.value,
            AgentRunStatus.EXECUTING_TOOLS.value,
            AgentRunStatus.PAUSED.value,
        }
        if status not in replanable_statuses:
            return jsonify({"error": "任务正在转换阶段，请稍后重试"}), 409

        existing = AgentConversationMessage.query.filter_by(
            client_message_id=client_message_id.strip()
        ).one_or_none()
        if existing is not None:
            return (
                jsonify(
                    {
                        "message": existing.to_dict(),
                        "replayed": True,
                        "run_id": run.id,
                        "plan_version": run.plan_version,
                    }
                ),
                200,
            )

        conversation = _conversation_for_run(run)
        if conversation is None:
            return jsonify({"error": "该任务没有关联会话，无法追加方向"}), 409

        message, new_plan = ConversationService().append_follow_up_direction(
            conversation,
            content=content.strip(),
            client_message_id=client_message_id.strip(),
            run=run,
        )
        return (
            jsonify(
                {
                    "message": message.to_dict(),
                    "plan_version": new_plan.plan_version,
                    "new_nodes": [
                        node.node_key
                        for node in new_plan.nodes
                        if node.node_key.startswith("direction_")
                    ],
                    "replayed": False,
                }
            ),
            201,
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ConversationError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


def _conversation_for_run(run: AgentRun):
    """通过 AgentTurn 反查 run 关联的会话（run 无直接 conversation_id 列）。"""
    from app.models.conversation import AgentTurn

    turn = AgentTurn.query.filter_by(run_id=run.id).order_by(AgentTurn.id.desc()).first()
    if turn is None:
        return None
    from app.models.conversation import AgentConversation

    return db.session.get(AgentConversation, turn.conversation_id)
