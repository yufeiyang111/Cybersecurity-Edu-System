"""Durable AgentRun state machine with optimistic concurrency control.

Every state transition is a single transaction that:
  1. validates the transition against the allowed transition table,
  2. updates status and increments state_version with an optimistic WHERE clause,
  3. appends an AgentEvent,
  4. appends an AuditEvent.

Routes, planners and tools never mutate ``run.status`` directly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import update

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.models.security import AuditEvent
from app.services.security_agent.contracts import (
    AGENT_EVENT_SCHEMA_VERSION,
    EVENT_RUN_COMPLETED,
    EVENT_RUN_STATE_CHANGED,
)

TERMINAL_STATUSES = frozenset(
    {
        AgentRunStatus.COMPLETED.value,
        AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
        AgentRunStatus.PARTIAL.value,
        AgentRunStatus.FAILED.value,
        AgentRunStatus.CANCELED.value,
    }
)

TRANSITIONS: dict[str, frozenset[str]] = {
    AgentRunStatus.CREATED.value: frozenset(
        {AgentRunStatus.QUEUED.value, AgentRunStatus.CANCELED.value}
    ),
    AgentRunStatus.QUEUED.value: frozenset(
        {AgentRunStatus.PREPARING.value, AgentRunStatus.CANCELED.value}
    ),
    AgentRunStatus.PREPARING.value: frozenset(
        {AgentRunStatus.PLANNING.value, AgentRunStatus.EXECUTING_TOOLS.value, AgentRunStatus.CANCELED.value}
    ),
    AgentRunStatus.MAPPING_REPOSITORY.value: frozenset(
        {AgentRunStatus.PLANNING.value, AgentRunStatus.EXECUTING_TOOLS.value, AgentRunStatus.CANCELED.value}
    ),
    AgentRunStatus.PLANNING.value: frozenset(
        {AgentRunStatus.VALIDATING_PLAN.value, AgentRunStatus.CANCELED.value}
    ),
    AgentRunStatus.VALIDATING_PLAN.value: frozenset(
        {AgentRunStatus.EXECUTING_TOOLS.value, AgentRunStatus.REPLANNING.value, AgentRunStatus.FAILED.value}
    ),
    AgentRunStatus.EXECUTING_TOOLS.value: frozenset(
        {
            AgentRunStatus.EVALUATING_EVIDENCE.value,
            AgentRunStatus.PAUSED.value,
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
    ),
    AgentRunStatus.EVALUATING_EVIDENCE.value: frozenset(
        {
            AgentRunStatus.EXECUTING_TOOLS.value,
            AgentRunStatus.REPLANNING.value,
            AgentRunStatus.DEEP_REVIEWING.value,
            AgentRunStatus.GENERATING_REPORT.value,
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
    ),
    AgentRunStatus.REPLANNING.value: frozenset(
        {
            AgentRunStatus.VALIDATING_PLAN.value,
            AgentRunStatus.PAUSED.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
    ),
    AgentRunStatus.DEEP_REVIEWING.value: frozenset(
        {
            AgentRunStatus.EVALUATING_EVIDENCE.value,
            AgentRunStatus.AWAITING_APPROVAL.value,
            AgentRunStatus.PAUSED.value,
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
    ),
    AgentRunStatus.AWAITING_APPROVAL.value: frozenset(
        {
            AgentRunStatus.EXECUTING_TOOLS.value,
            AgentRunStatus.PAUSED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
    ),
    AgentRunStatus.PAUSED.value: frozenset(
        {AgentRunStatus.EXECUTING_TOOLS.value, AgentRunStatus.CANCELED.value}
    ),
    AgentRunStatus.GENERATING_REPORT.value: frozenset(
        {
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }
    ),
}

for _status in TERMINAL_STATUSES:
    TRANSITIONS.setdefault(_status, frozenset())


class AgentStateError(ValueError):
    """Raised when a requested state transition is not allowed."""


class AgentVersionConflictError(AgentStateError):
    """Raised when the optimistic state_version update conflicts with a concurrent write."""


class AgentStateMachine:
    """Validates and persists run status transitions atomically."""

    @staticmethod
    def allowed_transitions(status: str) -> frozenset[str]:
        return TRANSITIONS.get(status, frozenset())

    @staticmethod
    def is_terminal(status: str) -> bool:
        return status in TERMINAL_STATUSES

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in TRANSITIONS.get(current, frozenset())

    def transition(
        self,
        run: AgentRun,
        target: AgentRunStatus | str,
        *,
        actor_id: int | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
        expected_version: int | None = None,
    ) -> int:
        """Apply one state transition; returns the new state_version."""
        target_value = target.value if isinstance(target, AgentRunStatus) else str(target)
        current_value = run.status.value if isinstance(run.status, AgentRunStatus) else str(run.status)

        if self.is_terminal(current_value):
            raise AgentStateError(f"已终止状态 {current_value} 不能继续转换")

        if not self.can_transition(current_value, target_value):
            raise AgentStateError(f"不允许的状态转换：{current_value} -> {target_value}")

        expected = run.state_version if expected_version is None else expected_version
        values: dict = {
            "status": target_value,
            "state_version": AgentRun.state_version + 1,
        }
        now = datetime.utcnow()
        if target_value in TERMINAL_STATUSES:
            values["finished_at"] = now
        if target_value == AgentRunStatus.PREPARING.value:
            values["started_at"] = now

        updated = db.session.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id, AgentRun.state_version == expected)
            .values(**values)
        )
        if updated.rowcount != 1:
            db.session.rollback()
            raise AgentVersionConflictError("状态版本冲突：工作进程需重新加载后重试")

        new_version = expected + 1
        sequence = self._append_event(
            run_id=run.id,
            event_type=EVENT_RUN_STATE_CHANGED,
            state_version=new_version,
            payload={
                "status": target_value,
                "from": current_value,
                "state_version": new_version,
                "reason": reason,
            },
            trace_id=trace_id,
        )
        run.state_version = new_version
        run.status = target_value
        run.last_event_sequence = sequence

        audit = AuditEvent(
            workspace_id=run.workspace_id,
            actor_id=actor_id,
            action=f"agent.run.{target_value.replace('_', '.')}",
            target_type="agent_run",
            target_id=run.id,
            metadata_json={
                "project_id": run.project_id,
                "snapshot_id": run.snapshot_id,
                "from": current_value,
                "to": target_value,
                "state_version": new_version,
                "event_sequence": sequence,
            },
        )
        db.session.add(audit)
        db.session.commit()
        return new_version

    def _append_event(
        self,
        *,
        run_id: int,
        event_type: str,
        state_version: int,
        payload: dict,
        trace_id: str | None,
    ) -> int:
        sequence = self._next_sequence(run_id)
        event = AgentEvent(
            run_id=run_id,
            sequence=sequence,
            state_version=state_version,
            event_type=event_type,
            schema_version=AGENT_EVENT_SCHEMA_VERSION,
            trace_id=trace_id,
            payload_json=payload,
        )
        db.session.add(event)
        return sequence

    def _next_sequence(self, run_id: int) -> int:
        from sqlalchemy import func

        maximum = db.session.query(func.coalesce(func.max(AgentEvent.sequence), 0)).filter(
            AgentEvent.run_id == run_id
        ).scalar()
        return int(maximum) + 1
