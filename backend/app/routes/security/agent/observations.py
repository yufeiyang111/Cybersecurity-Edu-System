"""AgentObservation endpoints: list (server-side paged), detail, review, remediation diff."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.observation_service import (
    ObservationReviewError,
    ObservationService,
)

from .. import projects_bp
from ..common import (
    AuthorizationError,
    PROJECT_ROLES,
    READ_ROLES,
    _current_user_id,
    _json_object,
    require_workspace_role,
)

_service = ObservationService()


def _agent_run_or_404(run_id: int) -> AgentRun | None:
    run = db.session.get(AgentRun, run_id)
    if run is None:
        return None
    require_workspace_role(run.workspace_id, _current_user_id(), READ_ROLES)
    return run


@projects_bp.route("/agent-runs/<int:run_id>/observations", methods=["GET"])
@jwt_required()
def list_agent_run_observations(run_id: int):
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        if page < 1 or not 1 <= page_size <= 100:
            return jsonify({"error": "page 必须大于 0，page_size 必须在 1 至 100 之间"}), 400
        rows, total = _service.list_for_run(run.id, page=page, page_size=page_size)
        return jsonify(
            {
                "items": [row.to_dict() for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route(
    "/agent-runs/<int:run_id>/observations/<int:observation_id>", methods=["GET"]
)
@jwt_required()
def get_agent_run_observation(run_id: int, observation_id: int):
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        observation = _service.get_or_none(run.id, observation_id)
        if observation is None:
            return jsonify({"error": "观察结论不存在"}), 404
        return jsonify({"observation": observation.to_dict(include_detail=True)})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route(
    "/agent-runs/<int:run_id>/observations/<int:observation_id>/review", methods=["POST"]
)
@jwt_required()
def review_agent_observation(run_id: int, observation_id: int):
    """Analyst/Owner 审核观察结论：confirmed / rejected / needs_more_evidence。"""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        data = _json_object()
        decision = data.get("decision")
        comment = data.get("comment") or ""
        if not isinstance(comment, str) or len(comment) > 1000:
            return jsonify({"error": "comment 不能超过 1000 字符"}), 400
        observation = _service.get_or_none(run.id, observation_id)
        if observation is None:
            return jsonify({"error": "观察结论不存在"}), 404
        reviewed = _service.review(
            run,
            observation,
            decision=decision,
            comment=comment,
            actor_id=_current_user_id(),
        )
        return jsonify({"observation": reviewed.to_dict(include_detail=True)})
    except ObservationReviewError as exc:
        return jsonify({"error": str(exc)}), 409
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route(
    "/agent-runs/<int:run_id>/observations/<int:observation_id>/remediation-diff",
    methods=["POST"],
)
@jwt_required()
def generate_observation_remediation_diff(run_id: int, observation_id: int):
    """对已确认观察生成受限修复 Diff（LLM + 范围校验；仅展示复制，不应用）。"""
    try:
        run = _agent_run_or_404(run_id, PROJECT_ROLES)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        observation = _service.get_or_none(run.id, observation_id)
        if observation is None:
            return jsonify({"error": "观察结论不存在"}), 404
        result = _service.generate_remediation_diff(
            run,
            observation,
            actor_id=_current_user_id(),
        )
        return jsonify(result)
    except ObservationReviewError as exc:
        return jsonify({"error": str(exc)}), 409
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
