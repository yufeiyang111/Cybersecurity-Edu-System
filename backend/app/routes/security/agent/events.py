"""Agent Run SSE：持久化事件可回放，Provider raw reasoning 仅瞬时转发。

Route 只负责鉴权和订阅，不推进 Worker。Last-Event-ID 仅作用于持久化事件；
Provider 原始 reasoning 不带 id、不可回放，并且只给任务发起人的活动连接。
"""
from __future__ import annotations

from flask import Response, current_app, jsonify, request, stream_with_context
from flask_jwt_extended import jwt_required

from app.services.security_agent.harness_v3.raw_reasoning import (
    get_provider_raw_reasoning_relay,
)
from app.services.security_agent.sse import agent_event_stream

from .. import projects_bp
from ..common import AuthorizationError, _current_user_id

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

    recipient_user_id = _current_user_id()
    raw_relay = get_provider_raw_reasoning_relay()

    def generate():
        subscription = raw_relay.subscribe(run, recipient_user_id)
        try:
            yield from agent_event_stream(
                run_id,
                last_event_id,
                heartbeat_seconds=heartbeat,
                poll_seconds=poll,
                raw_subscription=subscription,
            )
        finally:
            if subscription is not None:
                subscription.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-store, no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
