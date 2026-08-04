"""AgentRunService: durable run lifecycle orchestration (thin, state-only).

Plan execution lives in InlinePlanRunner; this service only creates, loads,
pauses, resumes, cancels and serializes runs, then dispatches the worker.
"""
from __future__ import annotations

import threading
import uuid

from flask import current_app

from app import db
from app.models.agent_runtime import (
    AgentMessage,
    AgentPlan,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentStepExecution,
    AgentToolCall,
)
from app.models.security import AuditEvent
from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.checkpoint_service import CheckpointService
from app.services.security_agent.contracts import (
    EVENT_RUN_CREATED,
    EVENT_RUN_PAUSED,
    EVENT_RUN_RESUMED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.runner import InlinePlanRunner
from app.services.security_agent.state_machine import AgentStateMachine


class AgentRunNotFoundError(ValueError):
    pass


class AgentRunStateError(ValueError):
    pass


class AgentRunService:
    def __init__(self) -> None:
        self._state = AgentStateMachine()
        self._events = EventService()
        self._artifacts = ArtifactService()
        self._checkpoints = CheckpointService()
        self._runner = InlinePlanRunner(
            state=self._state,
            events=self._events,
            artifacts=self._artifacts,
            checkpoints=self._checkpoints,
        )

    # ------------------------------------------------------------------ lifecycle

    def create_run(
        self,
        *,
        project,
        snapshot,
        user_id: int,
        goal_text: str,
        mode: str,
    ) -> AgentRun:
        mode_value = mode if mode in {item.value for item in AgentRunMode} else AgentRunMode.BASELINE.value
        trace_id = uuid.uuid4().hex
        run = AgentRun(
            workspace_id=project.workspace_id,
            project_id=project.id,
            snapshot_id=snapshot.id,
            created_by=user_id,
            goal_text=goal_text,
            mode=mode_value,
        )
        db.session.add(run)
        db.session.flush()

        self._events.emit(
            run,
            EVENT_RUN_CREATED,
            {"goal": goal_text[:200], "mode": mode_value},
            trace_id=trace_id,
        )
        db.session.add(
            AgentMessage(run_id=run.id, role="user", content=goal_text, message_type="user_goal")
        )
        db.session.add(
            AuditEvent(
                workspace_id=run.workspace_id,
                actor_id=user_id,
                action="agent.run.create",
                target_type="agent_run",
                target_id=run.id,
                metadata_json={
                    "project_id": run.project_id,
                    "snapshot_id": run.snapshot_id,
                    "mode": mode_value,
                    "event_sequence": run.last_event_sequence,
                },
            )
        )
        db.session.commit()
        self._state.transition(
            run,
            AgentRunStatus.QUEUED,
            actor_id=user_id,
            reason="运行已创建，等待执行",
            trace_id=trace_id,
        )
        self._dispatch(run, trace_id)
        db.session.refresh(run)
        return run

    def pause_run(self, run: AgentRun, actor_id: int | None) -> AgentRun:
        self._state.transition(
            run,
            AgentRunStatus.PAUSED,
            actor_id=actor_id,
            reason="用户暂停",
        )
        self._events.emit(run, EVENT_RUN_PAUSED, {"run_id": run.id})
        db.session.commit()
        return run

    def resume_run(self, run: AgentRun, actor_id: int | None) -> AgentRun:
        trace_id = uuid.uuid4().hex
        self._state.transition(
            run,
            AgentRunStatus.EXECUTING_TOOLS,
            actor_id=actor_id,
            reason="用户恢复",
        )
        self._events.emit(run, EVENT_RUN_RESUMED, {"run_id": run.id})
        db.session.commit()
        self._dispatch(run, trace_id)
        db.session.refresh(run)
        return run

    def cancel_run(self, run: AgentRun, actor_id: int | None) -> AgentRun:
        self._state.transition(
            run,
            AgentRunStatus.CANCELED,
            actor_id=actor_id,
            reason="用户取消",
        )
        self._runner._cancel_remaining_nodes(run)
        db.session.commit()
        return run

    def get_run_payload(self, run: AgentRun) -> dict:
        plan = (
            AgentPlan.query.filter_by(run_id=run.id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )
        steps = list(
            reversed(
                AgentStepExecution.query.filter_by(run_id=run.id)
                .order_by(AgentStepExecution.id.desc())
                .limit(50)
                .all()
            )
        )
        tool_calls = list(
            reversed(
                AgentToolCall.query.filter_by(run_id=run.id)
                .order_by(AgentToolCall.id.desc())
                .limit(50)
                .all()
            )
        )
        events = self._events.tail(run.id, limit=100)
        return {
            "run": run.to_dict(),
            "plan": plan.to_dict() if plan is not None else None,
            "steps": [step.to_dict() for step in steps],
            "tool_calls": [tool_call.to_dict() for tool_call in tool_calls],
            "events": [event.to_dict() for event in events],
            "last_sequence": run.last_event_sequence,
            "state_version": run.state_version,
        }

    def list_events(
        self, run_id: int, *, after_sequence: int = 0, limit: int = 200
    ) -> list:
        """Public event listing used by the events route (server-side bounded)."""
        return self._events.list_events(run_id, after_sequence=after_sequence, limit=limit)

    # ------------------------------------------------------------------ dispatch

    def _dispatch(self, run: AgentRun, trace_id: str) -> None:
        app = current_app._get_current_object()
        executor_mode = app.config.get("AGENT_RUN_EXECUTOR", "background")
        if executor_mode == "synchronous":
            self._runner.run(run.id, trace_id, app)
            return
        thread = threading.Thread(
            target=self._runner.run,
            args=(run.id, trace_id, app),
            name=f"agent-run-{run.id}",
            daemon=True,
        )
        thread.start()
