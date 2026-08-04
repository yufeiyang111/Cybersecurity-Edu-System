"""Persistence model for the replayable agent event stream."""
from __future__ import annotations

from datetime import datetime

from app import db


class AgentEvent(db.Model):
    __tablename__ = "agent_events"
    __table_args__ = (
        db.UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
        db.Index("ix_agent_events_run_sequence", "run_id", "sequence"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    state_version = db.Column(db.Integer, nullable=False, default=0)
    event_type = db.Column(db.String(64), nullable=False)
    schema_version = db.Column(db.Integer, nullable=False, default=1)
    trace_id = db.Column(db.String(64))
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    payload_json = db.Column(db.JSON)

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        """Return the full event envelope; payloads are small structured summaries only."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "state_version": self.state_version,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "payload": self.payload_json or {},
        }
