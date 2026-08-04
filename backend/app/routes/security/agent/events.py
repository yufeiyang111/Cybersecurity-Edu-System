"""Replayable SSE endpoint for agent run events.

The route only authorizes and streams persisted events; it never drives the
worker.  ``Last-Event-ID`` (or the ``after`` query param) requests replay.
"""
from __future__ import annotations

from flask import Response, current_app, jsonify, request, stream_with_context
from flask_jwt_extended import jwt_required

from app.services.security_agent.sse import agent_event_stream

from .. import projects_bp
from ..common import AuthorizationError

from .runs import _agent_run_or_404


@projects_bp.route("/agent-runs/<int:run_id>/events/stream", methods=["GET"])
@jwt_required()
def stream_agent_run_events(run_id: int):
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403

    last_event_id = request.headers.get("Last-Event-ID", type=int)
    if last_event_id is None:
        last_event_id = request.args.get("after", 0, type=int)
    heartbeat = current_app.config.get("AGENT_SSE_HEARTBEAT_SECONDS", 15)
    poll = current_app.config.get("AGENT_SSE_POLL_SECONDS", 0.5)

    def generate():
        yield from agent_event_stream(
            run_id,
            last_event_id,
            heartbeat_seconds=heartbeat,
            poll_seconds=poll,
        )

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
