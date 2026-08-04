"""Durable checkpoints so paused or interrupted runs can resume from the last saved state."""
from __future__ import annotations

from app import db
from app.models.agent_runtime import AgentCheckpoint, AgentRun


class CheckpointService:
    """Saves and restores per-run execution state snapshots."""

    def save(
        self,
        run: AgentRun,
        *,
        completed_node_keys: list[str],
        hypotheses: list[str] | None = None,
        artifact_refs: list[dict] | None = None,
    ) -> AgentCheckpoint:
        checkpoint = AgentCheckpoint(
            run_id=run.id,
            plan_version=run.plan_version,
            event_sequence=run.last_event_sequence,
            state_json={
                "plan_version": run.plan_version,
                "completed_node_keys": completed_node_keys,
                "hypotheses": hypotheses or [],
                "artifact_refs": artifact_refs or [],
            },
        )
        db.session.add(checkpoint)
        db.session.flush()
        return checkpoint

    def latest(self, run_id: int) -> AgentCheckpoint | None:
        return (
            AgentCheckpoint.query.filter(AgentCheckpoint.run_id == run_id)
            .order_by(AgentCheckpoint.id.desc())
            .first()
        )

    def restore(self, run_id: int) -> dict:
        checkpoint = self.latest(run_id)
        if checkpoint is None:
            return {"plan_version": 0, "completed_node_keys": [], "hypotheses": [], "artifact_refs": []}
        return checkpoint.state_json or {}
