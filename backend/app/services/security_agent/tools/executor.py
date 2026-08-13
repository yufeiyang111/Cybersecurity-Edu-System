"""ToolExecutor: one idempotent invocation boundary around registered tools.

T05 门禁链（spec §10.2，任何失败都在 Handler 前或结果落库前终止）：
存在性 → 模式 → 风险/审批 → 预算 → schema → 对象上下文 → 幂等复用 →
deadline/cancel → Handler → 超时改写 → 结果截断 → 持久化 → 事件。
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Callable

from app import db
from app.models.agent_approval import ApprovalStatus
from app.models.agent_runtime import (
    AgentPlanNode,
    AgentRun,
    AgentRunStatus,
    AgentStepExecution,
    AgentToolCall,
)
from app.services.security_agent.budget import budget_status
from app.services.security_agent.contracts import (
    EVENT_TOOL_COMPLETED,
    EVENT_TOOL_FAILED,
    EVENT_TOOL_STARTED,
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)
from app.services.security_agent.tools.deadline import deadline_for
from app.services.security_agent.tools.registry import ToolRegistry
from app.services.security_agent.tools.validator import (
    InputValidationError,
    validate_input,
)


class ToolExecutor:
    """执行一个工具一次：治理门禁 + 幂等 + 重试 + 超时 + 结果落库。"""

    def __init__(
        self,
        registry: ToolRegistry,
        events: EventService,
        heartbeat: Callable[[int], None] | None = None,
    ) -> None:
        self._registry = registry
        self._events = events
        # 长工具进度心跳回调（spec §10.3）：每次 attempt 边界调用，
        # 刷新 lease heartbeat_at，避免长工具期间被 watchdog 误判卡死。
        self._heartbeat = heartbeat

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
            return self._reject(run, node, step_execution, "AGENT_TOOL_FAILED",
                                 "节点没有绑定工具", trace_id)
        try:
            descriptor, handler = self._registry.resolve(node.tool_name)
        except KeyError:
            return self._reject(run, node, step_execution, "AGENT_TOOL_FAILED",
                                 f"工具未注册：{node.tool_name}", trace_id)

        blocked = self._policy_blocks(run, descriptor, input_payload)
        if blocked is not None:
            return self._reject(run, node, step_execution, blocked.error_code,
                                 blocked.summary, trace_id)

        logical_call_key = self._logical_call_key(run, node)
        arguments_digest = _digest(input_payload)

        replayed = self._replay_succeeded(run.id, logical_call_key, arguments_digest)
        if replayed is not None:
            return replayed

        max_attempts = self._max_attempts(descriptor)
        deadline = deadline_for(descriptor.timeout_seconds)
        final_result: ToolResult | None = None
        for attempt in range(max_attempts):
            attempt_number = step_execution.attempt_number + attempt
            self._notify_heartbeat(run.id)
            result, timed_out = self._run_attempt(
                run,
                node,
                step_execution,
                descriptor,
                handler,
                actor_id,
                trace_id,
                input_payload,
                logical_call_key,
                arguments_digest,
                attempt_number,
                deadline,
            )
            if result.status == "succeeded" or not self._can_retry(
                descriptor, result, attempt, max_attempts, deadline
            ):
                final_result = result
                break
            final_result = result
        return final_result or ToolResult(status="failed", summary="工具执行失败")

    def _notify_heartbeat(self, run_id: int) -> None:
        if self._heartbeat is None:
            return
        try:
            self._heartbeat(run_id)
        except Exception:
            db.session.rollback()

    # ---------------------------------------------------------------- gates

    def _policy_blocks(
        self,
        run: AgentRun,
        descriptor: ToolDescriptor,
        input_payload: dict | None,
    ) -> "ToolResult | None":
        """返回非 None 表示拒绝执行（Handler 不会被调用）。"""
        status = _status_value(run.status)
        if status in {
            AgentRunStatus.PAUSED.value,
            AgentRunStatus.CANCELED.value,
        }:
            return _blocked("AGENT_TOOL_FAILED", "Run 已暂停或取消，不再启动新工具")
        if descriptor.risk_level == "prohibited":
            return _blocked("AGENT_TOOL_NOT_ALLOWED", "prohibited 工具禁止执行")
        if _status_value(run.mode) not in descriptor.allowed_modes:
            return _blocked(
                "AGENT_TOOL_NOT_ALLOWED",
                f"运行模式 {run.mode} 不允许该工具",
            )
        budget = budget_status(run)
        if budget["exhausted"]:
            return _blocked("AGENT_BUDGET_EXHAUSTED", "Run 预算已耗尽")
        if descriptor.requires_approval and not self._has_approval(run.id):
            return _blocked("AGENT_APPROVAL_REQUIRED", "工具需要审批且尚未批准")
        try:
            validate_input(descriptor.input_schema, input_payload or {})
        except InputValidationError as exc:
            return _blocked("AGENT_TOOL_INPUT_INVALID", str(exc))
        return None

    def _run_attempt(
        self,
        run: AgentRun,
        node: AgentPlanNode,
        step_execution: AgentStepExecution,
        descriptor: ToolDescriptor,
        handler,
        actor_id: int | None,
        trace_id: str | None,
        input_payload: dict | None,
        logical_call_key: str,
        arguments_digest: str,
        attempt_number: int,
        deadline,
    ) -> tuple[ToolResult, bool]:
        idempotency_key = (
            f"{run.id}:{node.node_key}:{attempt_number}"
        )
        existing = AgentToolCall.query.filter_by(idempotency_key=idempotency_key).first()
        if existing is not None:
            return self._replay_result(existing), False

        tool_call = AgentToolCall(
            run_id=run.id,
            plan_node_id=node.id,
            step_execution_id=step_execution.id,
            tool_name=descriptor.name,
            tool_version=descriptor.version,
            status="running",
            risk_level=descriptor.risk_level,
            idempotency_key=idempotency_key,
            logical_call_key=logical_call_key,
            attempt_number=attempt_number,
            arguments_digest=arguments_digest,
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
            deadline_epoch=deadline.epoch,
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

        timed_out = deadline.expired()
        if timed_out and result.status == "succeeded":
            result = ToolResult(
                status="failed",
                summary="工具执行超过硬截止时间，迟到结果不写入成功",
                warning_codes=["AGENT_TOOL_TIMEOUT"],
                error_code="AGENT_TOOL_TIMEOUT",
                retryable=False,
            )

        latency_ms = int((time.monotonic() - started_epoch) * 1000)
        tool_call.status = result.status
        tool_call.output_summary = result.summary[: descriptor.max_output_chars]
        tool_call.artifact_refs = result.artifact_refs
        tool_call.warning_codes = result.warning_codes
        tool_call.error_code = result.error_code
        tool_call.retryable = result.retryable
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
            if result.warning_codes:
                self._events.emit(
                    run,
                    EVENT_WARNING_RAISED,
                    {"warning_codes": result.warning_codes, "node_key": node.node_key},
                    trace_id=trace_id,
                )
        db.session.commit()
        return result, timed_out

    # ---------------------------------------------------------------- retry

    @staticmethod
    def _max_attempts(descriptor: ToolDescriptor) -> int:
        if not descriptor.idempotent or descriptor.retry_policy is None:
            return 1
        return int(descriptor.retry_policy.get("max_attempts") or 1)

    @staticmethod
    def _can_retry(
        descriptor: ToolDescriptor,
        result: ToolResult,
        attempt: int,
        max_attempts: int,
        deadline,
    ) -> bool:
        if not descriptor.idempotent or descriptor.retry_policy is None:
            return False
        if result.status == "succeeded" or not result.retryable:
            return False
        if attempt + 1 >= max_attempts:
            return False
        if deadline.expired():
            return False
        allowlist = descriptor.retry_policy.get("retryable_warning_codes")
        if allowlist is None:
            return True
        return bool(set(result.warning_codes or []) & set(allowlist))

    # ---------------------------------------------------------------- idempotency

    @staticmethod
    def _logical_call_key(run: AgentRun, node: AgentPlanNode) -> str:
        return f"{run.id}:{node.node_key}"

    def _replay_succeeded(
        self, run_id: int, logical_call_key: str, arguments_digest: str
    ) -> ToolResult | None:
        """相同逻辑调用 + 相同参数且已成功的调用复用结果，不重复执行。"""
        existing = (
            AgentToolCall.query.filter_by(
                run_id=run_id,
                logical_call_key=logical_call_key,
                arguments_digest=arguments_digest,
                status="succeeded",
            )
            .order_by(AgentToolCall.attempt_number.desc())
            .first()
        )
        if existing is None:
            return None
        return self._replay_result(existing)

    def _replay_result(self, existing: AgentToolCall) -> ToolResult:
        return ToolResult(
            status=existing.status,
            summary=existing.output_summary or "（幂等重放：复用已完成的工具结果）",
            artifact_refs=existing.artifact_refs or [],
            warning_codes=existing.warning_codes or [],
            error_code=existing.error_code,
            metrics={"replayed": True},
        )

    # ---------------------------------------------------------------- approval

    @staticmethod
    def _has_approval(run_id: int) -> bool:
        from app.models.agent_approval import AgentApproval

        return (
            AgentApproval.query.filter_by(
                run_id=run_id, status=ApprovalStatus.APPROVED.value
            ).first()
            is not None
        )

    # ---------------------------------------------------------------- helpers

    def _reject(
        self,
        run: AgentRun,
        node: AgentPlanNode,
        step_execution: AgentStepExecution,
        error_code: str,
        summary: str,
        trace_id: str | None,
    ) -> ToolResult:
        """门禁拒绝：不调用 Handler，写 failed 事件后返回失败结果。"""
        result = ToolResult(
            status="failed",
            summary=summary[:4000],
            warning_codes=[error_code],
            error_code=error_code,
        )
        self._events.emit(
            run,
            EVENT_TOOL_FAILED,
            {
                "tool_call_id": None,
                "tool_name": node.tool_name,
                "node_key": node.node_key,
                "error_code": error_code,
                "summary": summary[:4000],
                "output_summary": summary[:4000],
            },
            trace_id=trace_id,
        )
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": [error_code], "node_key": node.node_key},
            trace_id=trace_id,
        )
        db.session.commit()
        return result


def _blocked(error_code: str, summary: str) -> ToolResult:
    return ToolResult(
        status="failed",
        summary=summary,
        warning_codes=[error_code],
        error_code=error_code,
    )


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _digest(input_payload: dict | None) -> str:
    raw = json.dumps(input_payload or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _summarize_input(input_payload: dict | None) -> str | None:
    if not input_payload:
        return None
    try:
        text = str(input_payload)
    except Exception:
        return None
    return text[:2000]
