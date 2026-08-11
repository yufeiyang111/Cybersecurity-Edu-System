"""AgentObservation endpoints: list (server-side paged) and detail with evidence."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.observation_service import ObservationService

from .. import projects_bp
from ..common import (
    AuthorizationError,
    READ_ROLES,
    _current_user_id,
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
