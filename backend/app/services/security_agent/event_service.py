"""AgentEvent persistence and replay queries."""
from __future__ import annotations

from sqlalchemy import func

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.contracts import AGENT_EVENT_SCHEMA_VERSION


class EventService:
    """Appends durable events and reads them back for replay.

    Sequence numbers are monotonic per run; the unique (run_id, sequence)
    constraint is the safety net for concurrent append attempts.
    """

    def emit(
        self,
        run: AgentRun,
        event_type: str,
        payload: dict | None = None,
        *,
        trace_id: str | None = None,
        state_version: int | None = None,
    ) -> AgentEvent:
        sequence = self._next_sequence(run.id)
        event = AgentEvent(
            run_id=run.id,
            sequence=sequence,
            state_version=run.state_version if state_version is None else state_version,
            event_type=event_type,
            schema_version=AGENT_EVENT_SCHEMA_VERSION,
            trace_id=trace_id,
            payload_json=payload or {},
        )
        db.session.add(event)
        run.last_event_sequence = sequence
        return event

    def list_events(
        self, run_id: int, *, after_sequence: int = 0, limit: int = 200
    ) -> list[AgentEvent]:
        query = AgentEvent.query.filter(
            AgentEvent.run_id == run_id, AgentEvent.sequence > after_sequence
        ).order_by(AgentEvent.sequence.asc())
        return query.limit(limit).all()

    def latest_sequence(self, run_id: int) -> int:
        value = (
            db.session.query(func.coalesce(func.max(AgentEvent.sequence), 0))
            .filter(AgentEvent.run_id == run_id)
            .scalar()
        )
        return int(value)

    def tail(self, run_id: int, limit: int = 100) -> list[AgentEvent]:
        rows = (
            AgentEvent.query.filter(AgentEvent.run_id == run_id)
            .order_by(AgentEvent.sequence.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))

    def _next_sequence(self, run_id: int) -> int:
        maximum = (
            db.session.query(func.coalesce(func.max(AgentEvent.sequence), 0))
            .filter(AgentEvent.run_id == run_id)
            .scalar()
        )
        return int(maximum) + 1
