"""ToolExecutor: one idempotent invocation boundary around registered tools."""
from __future__ import annotations

import time
from datetime import datetime

from app import db
from app.models.agent_runtime import AgentPlanNode, AgentRun, AgentStepExecution, AgentToolCall
from app.services.security_agent.contracts import (
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_FAILED,
    EVENT_TOOL_STARTED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)
from app.services.security_agent.tools.registry import ToolRegistry


class ToolExecutor:
    """Executes a tool once per (run, node, attempt) using its idempotency key."""

    def __init__(self, registry: ToolRegistry, events: EventService) -> None:
        self._registry = registry
        self._events = events

    def _idempotency_key(self, run_id: int, node_key: str, attempt_number: int) -> str:
        return f"{run_id}:{node_key}:{attempt_number}"

    def execute(
        self,
        run: AgentRun,
        node: AgentPlanNode,
        step_execution: AgentStepExecution,
        *,
        actor_id: int | None,
        trace_id: str | None,
        input_payload: dict | None = None,
    ) -> ToolResult:
        if not node.tool_name:
            raise ToolExecutionError("节点没有绑定工具")
        descriptor, handler = self._registry.resolve(node.tool_name)

        idempotency_key = self._idempotency_key(run.id, node.node_key, step_execution.attempt_number)
        existing = AgentToolCall.query.filter_by(idempotency_key=idempotency_key).first()
        if existing is not None:
            return self._replay_result(existing)

        tool_call = AgentToolCall(
            run_id=run.id,
            plan_node_id=node.id,
            step_execution_id=step_execution.id,
            tool_name=descriptor.name,
            tool_version=descriptor.version,
            status="running",
            risk_level=descriptor.risk_level,
            idempotency_key=idempotency_key,
            input_summary=_summarize_input(input_payload),
            started_at=datetime.utcnow(),
        )
        db.session.add(tool_call)
        db.session.flush()

        started_epoch = time.monotonic()
        self._events.emit(
            run,
            EVENT_TOOL_STARTED,
            {
                "tool_call_id": tool_call.id,
                "tool_name": descriptor.name,
                "tool_version": descriptor.version,
                "node_key": node.node_key,
                "risk_level": descriptor.risk_level,
                "input_summary": tool_call.input_summary or "",
            },
            trace_id=trace_id,
        )
        db.session.commit()

        ctx = ToolExecutionContext(
            run=run,
            plan_node=node,
            step_execution=step_execution,
            tool_call=tool_call,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            snapshot_id=run.snapshot_id,
            actor_id=actor_id,
            trace_id=trace_id,
            input=input_payload or {},
        )

        try:
            result = handler(ctx)
        except ToolExecutionError as exc:
            result = ToolResult(
                status="failed",
                summary=str(exc),
                warning_codes=[exc.warning_code],
                error_code="AGENT_TOOL_FAILED",
            )
        except Exception:
            db.session.rollback()
            result = ToolResult(
                status="failed",
                summary="工具执行异常",
                warning_codes=["AGENT_TOOL_FAILED"],
                error_code="AGENT_TOOL_FAILED",
            )

        latency_ms = int((time.monotonic() - started_epoch) * 1000)
        tool_call.status = result.status
        tool_call.output_summary = result.summary
        tool_call.artifact_refs = result.artifact_refs
        tool_call.warning_codes = result.warning_codes
        tool_call.error_code = result.error_code
        tool_call.latency_ms = latency_ms
        tool_call.finished_at = datetime.utcnow()
        run.tool_call_count = (run.tool_call_count or 0) + 1
        db.session.add(tool_call)

        if result.status == "succeeded":
            self._events.emit(
                run,
                EVENT_TOOL_COMPLETED,
                {
                    "tool_call_id": tool_call.id,
                    "tool_name": descriptor.name,
                    "node_key": node.node_key,
                    "summary": result.summary,
                    "output_summary": result.summary,
                    "latency_ms": latency_ms,
                    "metrics": result.metrics,
                    "artifact_refs": result.artifact_refs,
                },
                trace_id=trace_id,
            )
        else:
            self._events.emit(
                run,
                EVENT_TOOL_FAILED,
                {
                    "tool_call_id": tool_call.id,
                    "tool_name": descriptor.name,
                    "node_key": node.node_key,
                    "error_code": result.error_code,
                    "summary": result.summary,
                    "output_summary": result.summary,
                },
                trace_id=trace_id,
            )
        db.session.commit()
        return result

    def _replay_result(self, existing: AgentToolCall) -> ToolResult:
        """Idempotent replay: return the stored outcome without re-executing."""
        return ToolResult(
            status=existing.status,
            summary=existing.output_summary or "（幂等重放：复用已完成的工具结果）",
            artifact_refs=existing.artifact_refs or [],
            warning_codes=existing.warning_codes or [],
            error_code=existing.error_code,
            metrics={"replayed": True},
        )


def _summarize_input(input_payload: dict | None) -> str | None:
    if not input_payload:
        return None
    try:
        text = str(input_payload)
    except Exception:
        return None
    return text[:2000]
