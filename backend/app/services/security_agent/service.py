"""AgentRunService: durable run lifecycle orchestration (thin, state-only).

Plan execution lives in InlinePlanRunner; this service only creates, loads,
pauses, resumes, cancels and serializes runs, then dispatches the worker.
"""
from __future__ import annotations

import threading
import uuid

from flask import current_app

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentDecisionRecord,
    AgentMessage,
    AgentPlan,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentStepExecution,
    AgentToolCall,
)
from app.models.security import AuditEvent
from app.services.agent_observability import AgentLogger
from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.checkpoint_service import CheckpointService
from app.services.security_agent.contracts import (
    EVENT_RUN_CREATED,
    EVENT_RUN_PAUSED,
    EVENT_RUN_RESUMED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.feature_flags import AgentFeatureFlags
from app.services.security_agent.runner import InlinePlanRunner
from app.services.security_agent.run_statistics import build_run_statistics
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
        self._agent_log = AgentLogger()
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
        budget: dict | None = None,
    ) -> AgentRun:
        mode_value = mode if mode in {item.value for item in AgentRunMode} else AgentRunMode.BASELINE.value
        trace_id = uuid.uuid4().hex
        budget_values = _parse_budget(budget or {})
        feature_flags_snapshot = AgentFeatureFlags().for_workspace(
            project.workspace_id
        ).as_dict()
        run = AgentRun(
            workspace_id=project.workspace_id,
            project_id=project.id,
            snapshot_id=snapshot.id,
            created_by=user_id,
            goal_text=goal_text,
            mode=mode_value,
            feature_flags_snapshot_json=feature_flags_snapshot,
            **budget_values,
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
                    "feature_flags_snapshot": feature_flags_snapshot,
                    "event_sequence": run.last_event_sequence,
                },
            )
        )
        db.session.commit()
        self._state.transition(
            run,
            AgentRunStatus.QUEUED,
            actor_id=user_id,
            reason="杩愯宸插垱寤猴紝绛夊緟鎵ц",
            trace_id=trace_id,
        )
        self._agent_log.run_event("run.created", run, trace_id=trace_id)
        self._dispatch(run, trace_id)
        db.session.refresh(run)
        return run

    def pause_run(self, run: AgentRun, actor_id: int | None) -> AgentRun:
        self._state.transition(
            run,
            AgentRunStatus.PAUSED,
            actor_id=actor_id,
            reason="鐢ㄦ埛鏆傚仠",
        )
        self._events.emit(run, EVENT_RUN_PAUSED, {"run_id": run.id})
        self._agent_log.run_event("run.paused", run)
        db.session.commit()
        return run

    def resume_run(self, run: AgentRun, actor_id: int | None) -> AgentRun:
        trace_id = uuid.uuid4().hex
        self._state.transition(
            run,
            AgentRunStatus.EXECUTING_TOOLS,
            actor_id=actor_id,
            reason="鐢ㄦ埛鎭㈠",
        )
        self._events.emit(run, EVENT_RUN_RESUMED, {"run_id": run.id})
        self._agent_log.run_event("run.resumed", run, trace_id=trace_id)
        db.session.commit()
        self._dispatch(run, trace_id)
        db.session.refresh(run)
        return run

    def cancel_run(self, run: AgentRun, actor_id: int | None) -> AgentRun:
        """以可审计的两阶段流程取消任务。

        ``cancel_requested`` 不是终态：先记录取消意图，再取消未执行节点，最后
        才写入 ``canceled``。这样前端和审计日志都能区分“正在收尾”与“已停止”。
        """
        current_status = _status_value(run.status)
        if current_status != AgentRunStatus.CANCEL_REQUESTED.value:
            self._state.transition(
                run,
                AgentRunStatus.CANCEL_REQUESTED,
                actor_id=actor_id,
                reason="用户请求取消，等待安全收尾",
            )
            self._agent_log.run_event("run.cancel_requested", run)

        self._runner._cancel_remaining_nodes(run)
        self._state.transition(
            run,
            AgentRunStatus.CANCELED,
            actor_id=actor_id,
            reason="未执行节点已取消，任务安全结束",
        )
        self._agent_log.run_event("run.canceled", run)
        return run
    def get_run_payload(self, run: AgentRun) -> dict:
        db.session.refresh(run)
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
        messages = (
            AgentMessage.query.filter_by(run_id=run.id)
            .order_by(AgentMessage.id.asc())
            .all()
        )
        decisions = list(
            reversed(
                AgentDecisionRecord.query.filter_by(run_id=run.id)
                .order_by(AgentDecisionRecord.id.desc())
                .limit(20)
                .all()
            )
        )
        stats = build_run_statistics(run, plan)
        execution_feature_flags, feature_flag_source = _execution_feature_flags(run)
        workspace_feature_flags = AgentFeatureFlags().for_workspace(
            run.workspace_id
        ).as_dict()
        run_payload = run.to_dict()
        run_payload.update(
            {
                "execution_feature_flags": execution_feature_flags,
                "execution_feature_flag_source": feature_flag_source,
                "workspace_feature_flags": workspace_feature_flags,
            }
        )
        return {
            "run": run_payload,
            "plan": plan.to_dict() if plan is not None else None,
            "stats": stats,
            "steps": [step.to_dict() for step in steps],
            "tool_calls": [tool_call.to_dict() for tool_call in tool_calls],
            "events": [event.to_dict() for event in events],
            "messages": [message.to_dict() for message in messages],
            "decisions": [record.to_dict() for record in decisions],
            "scan_summary": _scan_summary(run.snapshot_id),
            "last_sequence": run.last_event_sequence,
            "state_version": run.state_version,
            "feature_flags": execution_feature_flags,
            "feature_flag_source": feature_flag_source,
            "workspace_feature_flags": workspace_feature_flags,
        }

    def list_events(
        self, run_id: int, *, after_sequence: int = 0, limit: int = 200
    ) -> list:
        """Public event listing used by the events route (server-side bounded)."""
        return self._events.list_events(run_id, after_sequence=after_sequence, limit=limit)

    # ------------------------------------------------------------------ dispatch

    def execute_open_run(self, run_id: int, trace_id: str) -> None:
        """在独立执行上下文（RQ worker）中运行为开放状态的 run。"""
        from flask import current_app as _app

        self._runner.run(run_id, trace_id, _app._get_current_object())

    def _dispatch(self, run: AgentRun, trace_id: str) -> None:
        app = current_app._get_current_object()
        executor_mode = app.config.get("AGENT_RUN_EXECUTOR", "background")
        if executor_mode == "synchronous":
            self._runner.run(run.id, trace_id, app)
            return
        rq_enabled = executor_mode == "rq" or bool(app.config.get("RQ_ASYNC", False))
        if rq_enabled:
            try:
                self._enqueue(run.id, trace_id, app)
                return
            except Exception:
                # Redis 不可用时不阻断 run 生命周期；降级为进程内线程并留痕。
                current_app.logger.warning(
                    "agent run enqueue failed, falling back to in-process thread "
                    "(run_id=%s trace_id=%s)",
                    run.id,
                    trace_id,
                    exc_info=True,
                )
        thread = threading.Thread(
            target=self._runner.run,
            args=(run.id, trace_id, app),
            name=f"agent-run-{run.id}",
            daemon=True,
        )
        thread.start()

    def _enqueue(self, run_id: int, trace_id: str, app) -> str:
        from redis import Redis
        from rq import Queue

        from app.services.security_agent.runner import run_queued_agent_run

        queue = Queue(
            app.config["RQ_QUEUE_NAME"],
            connection=Redis.from_url(app.config["REDIS_URL"]),
        )
        job = queue.enqueue(
            run_queued_agent_run,
            run_id,
            trace_id,
            job_id=f"agent-run-{run_id}-{trace_id}",
            result_ttl=86400,
            failure_ttl=604800,
        )
        return job.id




def _status_value(value) -> str:
    """兼容 SQLAlchemy Enum 与字符串状态。"""
    return value.value if hasattr(value, "value") else str(value)
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

_BUDGET_FIELDS = (
    "max_llm_calls",
    "max_tool_calls",
    "max_total_tokens",
    "max_wall_clock_seconds",
)


def _parse_budget(budget: dict) -> dict:
    """Validate optional run budget fields; unknown/absent fields are ignored."""
    if not isinstance(budget, dict):
        raise ValueError("budget 必须是对象")
    values: dict = {}
    for field in _BUDGET_FIELDS:
        if field not in budget or budget[field] is None:
            continue
        try:
            value = int(budget[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} 必须是正整数") from exc
        if value < 1:
            raise ValueError(f"{field} 必须是正整数")
        values[field] = value
    if "max_estimated_cost" in budget and budget["max_estimated_cost"] is not None:
        try:
            cost = float(budget["max_estimated_cost"])
        except (TypeError, ValueError) as exc:
            raise ValueError("max_estimated_cost 必须是正数") from exc
        if cost <= 0:
            raise ValueError("max_estimated_cost 必须是正数")
        values["max_estimated_cost"] = cost
    return values


def _execution_feature_flags(run: AgentRun) -> tuple[dict, str]:
    """返回本次 Run 的实际协议快照及其证据来源。"""
    flags = AgentFeatureFlags()
    snapshot = flags.snapshot_for_run(run)
    if snapshot is not None:
        return snapshot.as_dict(), "run_snapshot"

    observed = _observed_legacy_feature_flags(run)
    if observed is not None:
        return observed, "legacy_observed"

    return flags.for_workspace(run.workspace_id).as_dict(), "workspace_fallback"


def _observed_legacy_feature_flags(run: AgentRun) -> dict | None:
    """仅凭已持久化的 v2 事件还原没有快照的历史 Run，避免伪造执行事实。"""
    has_v2_event = (
        AgentEvent.query.filter(
            AgentEvent.run_id == run.id,
            AgentEvent.schema_version >= 2,
        )
        .limit(1)
        .first()
        is not None
    )
    if not has_v2_event:
        has_v2_event = (
            AgentEvent.query.filter(
                AgentEvent.run_id == run.id,
                AgentEvent.event_type.like("item.%"),
            )
            .limit(1)
            .first()
            is not None
        )
    if not has_v2_event:
        return None

    has_reasoning_summary = (
        AgentEvent.query.filter(
            AgentEvent.run_id == run.id,
            AgentEvent.event_type.like("item.reasoning_summary.%"),
        )
        .limit(1)
        .first()
        is not None
    )
    mode = getattr(getattr(run, "mode", None), "value", getattr(run, "mode", None))
    is_loop_mode = mode != AgentRunMode.BASELINE.value
    has_loop_activity = (
        has_reasoning_summary
        or int(getattr(run, "iteration_count", 0) or 0) > 0
        or int(getattr(run, "llm_call_count", 0) or 0) > 0
    )
    return {
        "loop_v2": bool(is_loop_mode and has_loop_activity),
        "event_schema_v2": True,
        "timeline_v2": True,
    }


def _scan_summary(snapshot_id: int) -> dict | None:
    from app.models.security import ScanTask, SecurityFinding

    task = (
        ScanTask.query.filter_by(snapshot_id=snapshot_id)
        .order_by(ScanTask.id.desc())
        .first()
    )
    if task is None:
        return None
    rows = SecurityFinding.query.filter_by(task_id=task.id).all()
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in rows:
        severity = (
            finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
        )
        counts[severity] = counts.get(severity, 0) + 1
    top = sorted(
        rows,
        key=lambda item: (
            SEVERITY_ORDER.get(
                item.severity.value if hasattr(item.severity, "value") else str(item.severity), 9
            ),
            item.file_path,
        ),
    )[:10]
    return {
        "task_id": task.id,
        "findings_count": len(rows),
        "severity_counts": counts,
        "languages": (task.summary_json or {}).get("languages", []),
        "top_findings": [
            {
                "id": item.id,
                "rule_id": item.rule_id,
                "severity": item.severity.value
                if hasattr(item.severity, "value")
                else str(item.severity),
                "file_path": item.file_path,
                "start_line": item.start_line,
                "message": item.message[:120],
            }
            for item in top
        ],
    }
