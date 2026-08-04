"""Replayable SSE stream over the durable AgentEvent table.

The stream emits persisted events in sequence order, honors ``Last-Event-ID``
for replay, sends 15-second heartbeat comments and closes once the run is
terminal and fully caught up.  It never executes business logic.
"""
from __future__ import annotations

import json
import time

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.state_machine import TERMINAL_STATUSES


def _event_lines(agent_event: AgentEvent) -> str:
    payload = {
        "run_id": agent_event.run_id,
        "sequence": agent_event.sequence,
        "state_version": agent_event.state_version,
        "event_type": agent_event.event_type,
        "occurred_at": agent_event.occurred_at.isoformat() if agent_event.occurred_at else None,
        "payload": agent_event.payload_json or {},
    }
    return (
        f"id: {agent_event.sequence}\n"
        f"event: {agent_event.event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


def agent_event_stream(
    run_id: int,
    last_event_id: int,
    *,
    heartbeat_seconds: int = 15,
    poll_seconds: float = 0.5,
) -> object:
    """Yield SSE frames for one agent run; used with flask Response + stream_with_context."""
    sequence = max(0, int(last_event_id or 0))
    last_yield_epoch = time.monotonic()

    while True:
        try:
            with db.session() as session:
                events = (
                    session.query(AgentEvent)
                    .filter(AgentEvent.run_id == run_id, AgentEvent.sequence > sequence)
                    .order_by(AgentEvent.sequence.asc())
                    .limit(500)
                    .all()
                )
                for agent_event in events:
                    sequence = agent_event.sequence
                    yield _event_lines(agent_event)

                run = session.get(AgentRun, run_id)
                if run is None:
                    break
                status = run.status.value if hasattr(run.status, "value") else run.status
                caught_up = run.last_event_sequence <= sequence
                if status in TERMINAL_STATUSES and caught_up:
                    break
        finally:
            db.session.remove()

        now = time.monotonic()
        if now - last_yield_epoch >= heartbeat_seconds:
            yield ": ping\n\n"
            last_yield_epoch = now
        time.sleep(poll_seconds)
