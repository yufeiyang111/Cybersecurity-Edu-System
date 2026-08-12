"""Durable checkpoints so paused or interrupted runs can resume from the last saved state.

T09：Checkpoint 记录 iteration、context watermark、current item、plan version、
pending control watermark、budget、lease owner 与 digest；只保存可序列化业务
状态，不保存 Python 对象、Provider 客户端或隐式闭包。
"""
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
        iteration: int | None = None,
        context_watermark: int | None = None,
        current_item_public_id: str | None = None,
        lease_owner: str | None = None,
        pending_control_watermark: int | None = None,
        budget_snapshot: dict | None = None,
        checkpoint_digest: str | None = None,
    ) -> AgentCheckpoint:
        checkpoint = AgentCheckpoint(
            run_id=run.id,
            plan_version=run.plan_version,
            event_sequence=run.last_event_sequence,
            iteration=iteration or 0,
            context_watermark=context_watermark or 0,
            current_item_public_id=current_item_public_id,
            lease_owner=lease_owner,
            checkpoint_digest=checkpoint_digest,
            state_json={
                "plan_version": run.plan_version,
                "completed_node_keys": completed_node_keys,
                "hypotheses": hypotheses or [],
                "artifact_refs": artifact_refs or [],
                "iteration": iteration or 0,
                "context_watermark": context_watermark or 0,
                "current_item_public_id": current_item_public_id,
                "lease_owner": lease_owner,
                "pending_control_watermark": pending_control_watermark or 0,
                "budget_snapshot": budget_snapshot or {},
                "checkpoint_digest": checkpoint_digest,
            },
        )
        db.session.add(checkpoint)
        db.session.flush()
        run.last_checkpoint_id = checkpoint.id
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
            return {
                "plan_version": 0,
                "completed_node_keys": [],
                "hypotheses": [],
                "artifact_refs": [],
                "iteration": 0,
                "context_watermark": 0,
                "current_item_public_id": None,
                "lease_owner": None,
                "pending_control_watermark": 0,
                "budget_snapshot": {},
                "checkpoint_digest": None,
            }
        return checkpoint.state_json or {}
