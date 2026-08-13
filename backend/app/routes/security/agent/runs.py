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
        from app.services.security_agent.timeline.snapshot_service import SnapshotService

        payload = _service.get_run_payload(run)
        snapshot = SnapshotService().build_snapshot(run.id)
        payload["items"] = snapshot["items"]
        payload["snapshot_watermark"] = snapshot["snapshot_watermark"]
        return jsonify(payload)
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/items", methods=["GET"])
@jwt_required()
def list_agent_run_items(run_id: int):
    """v2 Items 服务端分页（Route 只鉴权、校验参数并调用 Service）。"""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 50, type=int)
        item_type = request.args.get("item_type")
        if page < 1 or not 1 <= page_size <= 200:
            return jsonify({"error": "page 必须大于 0，page_size 必须在 1 至 200 之间"}), 400
        if item_type is not None and (not isinstance(item_type, str) or not item_type.strip()):
            return jsonify({"error": "item_type 必须是字符串"}), 400
        from app.services.security_agent.timeline.snapshot_service import SnapshotService

        rows, total = SnapshotService().list_items(
            run.id,
            page=page,
            page_size=page_size,
            item_type=(item_type or "").strip() or None,
        )
        return jsonify(
            {
                "items": [item.to_dict() for item in rows],
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                },
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


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


@projects_bp.route("/agent-runs/<int:run_id>/retry", methods=["POST"])
@jwt_required()
def retry_agent_run(run_id: int):
    """Retry API（spec §16.2，L-05）：只接受可恢复的 failed/partial Run。

    转为 system_retry 控制输入 + QUEUED 重新入队 dispatch；HTTP 线程
    不同步执行工具或推进 Loop。
    """
    import uuid

    from app.services.security_agent.loop.control_inputs import (
        ControlInputError,
        ControlInputService,
    )

    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        data = _json_object()
        client_request_id = data.get("client_request_id")
        if client_request_id is None:
            client_request_id = f"retry-{uuid.uuid4().hex[:12]}"
        if not isinstance(client_request_id, str) or not client_request_id.strip():
            return jsonify({"error": "client_request_id 必须是字符串"}), 400

        control = ControlInputService().enqueue(
            run,
            input_type="system_retry",
            payload={},
            client_request_id=client_request_id.strip(),
            created_by=_current_user_id(),
        )
        _service._state.retry(
            run,
            actor_id=_current_user_id(),
            reason=f"用户重试（client_request_id={client_request_id.strip()}）",
        )
        trace_id = uuid.uuid4().hex
        _service._dispatch(run, trace_id)
        db.session.refresh(run)
        return jsonify(
            {
                "run": run.to_dict(),
                "control_input": control.to_dict(),
                "retried": True,
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except AgentStateError as exc:
        return jsonify({"error": str(exc)}), 409
    except ControlInputError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-runs/<int:run_id>/messages", methods=["POST"])
@jwt_required()
def post_agent_run_message(run_id: int):
    """用户对运行中的 Agent 追加方向（T07）：只幂等写入 Message + Control
    Input + 事件并唤醒，不同步创建计划或执行工具。

    幂等：相同 client_message_id 重试返回既有消息与控制输入（replayed=True）。
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

        message, control = ConversationService().append_follow_up_direction(
            conversation,
            content=content.strip(),
            client_message_id=client_message_id.strip(),
            run=run,
        )
        return (
            jsonify(
                {
                    "message": message.to_dict(),
                    "control_input": control.to_dict(),
                    "plan_version": run.plan_version,
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


@projects_bp.route("/agent-runs/<int:run_id>/control-inputs", methods=["POST"])
@jwt_required()
def post_agent_run_control_input(run_id: int):
    """统一控制输入端点（T07，spec §16.2）：HTTP 线程只幂等入队，不执行动作。"""
    from app.services.security_agent.loop.control_inputs import (
        ALLOWED_INPUT_TYPES,
        ControlInputError,
        ControlInputService,
    )

    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404

        data = _json_object()
        client_request_id = data.get("client_request_id")
        input_type = data.get("type")
        payload = data.get("payload") or {}
        if not isinstance(client_request_id, str) or not client_request_id.strip():
            return jsonify({"error": "缺少 client_request_id（用于防重复提交）"}), 400
        if input_type not in ALLOWED_INPUT_TYPES:
            return (
                jsonify(
                    {
                        "error": f"type 必须是 {'、'.join(sorted(ALLOWED_INPUT_TYPES))} 之一"
                    }
                ),
                400,
            )
        if not isinstance(payload, dict):
            return jsonify({"error": "payload 必须是对象"}), 400

        control = ControlInputService().enqueue(
            run,
            input_type=input_type,
            payload=payload,
            client_request_id=client_request_id.strip(),
            created_by=_current_user_id(),
        )
        return jsonify({"control_input": control.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ControlInputError as exc:
        return jsonify({"error": str(exc)}), 400


def _conversation_for_run(run: AgentRun):
    """通过 AgentTurn 反查 run 关联的会话（run 无直接 conversation_id 列）。"""
    from app.models.conversation import AgentTurn

    turn = AgentTurn.query.filter_by(run_id=run.id).order_by(AgentTurn.id.desc()).first()
    if turn is None:
        return None
    from app.models.conversation import AgentConversation

    return db.session.get(AgentConversation, turn.conversation_id)
