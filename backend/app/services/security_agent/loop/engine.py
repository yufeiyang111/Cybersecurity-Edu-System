# -*- coding: utf-8 -*-
"""AgentLoopEngine（T08，spec §6）：模型在环的单步推进与循环编排。

每轮严格执行：应用控制输入 → 检查硬限制 → 组装上下文 → 模型决策 →
标准化 Action → 策略校验与执行 → 持久化 Item/Event → Checkpoint → 下一轮。
模型只能产生冻结动作（tool_calls/plan_update/request_approval/ask_user/
final_answer）；工具执行经过 ToolExecutor 门禁；终态一律由
CompletionEvaluator 产生。baseline 模式为显式"策略工作流"降级。
"""
from __future__ import annotations

import json
import logging

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
    AgentStepExecution,
)
from app.services.security_agent.budget import budget_status
from app.services.security_agent.loop.actions import ActionKind
from app.services.security_agent.loop.completion_evaluator import (
    CompletionEvaluator,
)
from app.services.security_agent.loop.context_assembler import (
    SYSTEM_SECURITY_BOUNDARY,
    ContextAssembler,
)
from app.services.security_agent.loop.control_inputs import ControlInputService
from app.services.security_agent.model.contracts import (
    AgentModelMessage,
    AgentModelRequest,
    AgentModelResponse,
    AgentModelToolCall,
    AgentToolDefinition,
    ContractValidationError,
)
from app.services.security_agent.model.context_renderer import append_tool_results
from app.services.security_agent.model.gateway import AgentModelGateway
from app.services.security_agent.planning.scheduler import PlanScheduler
from app.services.security_agent.state_machine import AgentStateMachine
from app.services.security_agent.timeline.contracts import (
    EVENT_CHECKPOINT_CREATED,
    EVENT_TOOL_CALL_COMPLETED,
    EVENT_TOOL_CALL_STARTED,
    EVENT_TOOL_RESULT_CREATED,
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 20
DEFAULT_MAX_TOOL_CALLS = 30
DEFAULT_MAX_CONSECUTIVE_MODEL_ERRORS = 2
DEFAULT_MAX_SAME_TOOL_SAME_ARGS = 2
_MAX_TOOL_RESULT_SUMMARY_CHARS = 2000


class AgentLoopEngine:
    """一次只推进一个安全状态；不直接拼 Prompt 大段、不自行执行工具。"""

    def __init__(
        self,
        *,
        provider=None,
        gateway: AgentModelGateway | None = None,
        registry=None,
        events=None,
        writer: EventWriter | None = None,
        scheduler: PlanScheduler | None = None,
        controls: ControlInputService | None = None,
        assembler: ContextAssembler | None = None,
        evaluator: CompletionEvaluator | None = None,
        state: AgentStateMachine | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
        max_consecutive_model_errors: int = DEFAULT_MAX_CONSECUTIVE_MODEL_ERRORS,
        max_same_tool_same_args: int = DEFAULT_MAX_SAME_TOOL_SAME_ARGS,
    ) -> None:
        self._provider = provider
        self._gateway = gateway or AgentModelGateway()
        self._registry = registry if registry is not None else get_tool_registry()
        self._events = events
        self._writer = writer or EventWriter()
        self._scheduler = scheduler or PlanScheduler()
        self._controls = controls or ControlInputService()
        self._assembler = assembler or ContextAssembler()
        self._evaluator = evaluator or CompletionEvaluator()
        self._state = state or AgentStateMachine()
        self._tools = ToolExecutor(self._registry, events or EventServiceLike())
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_consecutive_model_errors = max_consecutive_model_errors
        self.max_same_tool_same_args = max_same_tool_same_args
        self._consecutive_model_errors = 0
        self._same_tool_calls: dict[str, int] = {}
        self._tool_results: list[dict] = []
        self._assistant_tool_calls: list[AgentModelToolCall] = []
        self._feedback: list[str] = []
        self._baseline_done = False

    def supported_actions(self) -> set[str]:
        return {kind.value for kind in ActionKind}

    # ---------------------------------------------------------------- loop

    def run_until_interrupt(self, run_id: int, trace_id: str) -> str:
        """推进到中断或终态；返回终态名或 interrupted。"""
        while True:
            run = db.session.get(AgentRun, run_id)
            if run is None:
                return "failed"
            if self._is_terminal(run):
                return self._status_value(run.status)
            result = self.advance_once(run, trace_id)
            if result != "continue":
                return result

    def advance_once(self, run: AgentRun, trace_id: str) -> str:
        """单轮推进：控制输入 → 硬限制 → 上下文 → 模型 → 动作 → 检查点。"""
        terminal = self._apply_control_inputs(run, trace_id)
        if terminal:
            return terminal

        run = db.session.get(AgentRun, run.id)
        if run is None:
            return "failed"
        if self._status_value(run.status) == AgentRunStatus.PAUSED.value:
            return "interrupted"

        limit = self._enforce_limits(run, trace_id)
        if limit:
            return limit

        if self._status_value(run.mode) == "baseline" and not self._baseline_done:
            self._run_baseline_dag(run, trace_id)
            return "continue"

        request = self._build_request(run)
        response = self._next_model_turn(run, request, trace_id)
        if response is None:
            return "continue"

        try:
            action = response.to_action()
        except ContractValidationError as exc:
            logger.warning(
                "Agent model returned invalid action (run_id=%s, error=%s)",
                run.id,
                type(exc).__name__,
            )
            return self._finalize(
                run, "partial", ["AGENT_MODEL_ACTION_INVALID"], trace_id
            )

        run = db.session.get(AgentRun, run.id)
        if run is None:
            return "failed"
        run.iteration_count = (run.iteration_count or 0) + 1
        terminal = self._dispatch_action(run, action, trace_id)
        if terminal != "continue":
            run.context_watermark = run.last_event_sequence
            db.session.commit()
            return terminal

        run = db.session.get(AgentRun, run.id)
        if run is None:
            return "failed"
        run.context_watermark = run.last_event_sequence
        self._writer.emit(
            run,
            event_type=EVENT_CHECKPOINT_CREATED,
            payload={
                "iteration": run.iteration_count,
                "context_watermark": run.context_watermark,
            },
            trace_id=trace_id,
        )
        db.session.commit()
        return "continue"

    # ---------------------------------------------------------------- model

    def _next_model_turn(
        self, run: AgentRun, request: AgentModelRequest, trace_id: str
    ) -> AgentModelResponse | None:
        provider = self._provider
        if provider is None:
            from app.services.llm.provider_selector import select_provider

            provider = select_provider(user_id=run.created_by, operation="agent")
        response = self._gateway.next_turn(
            request,
            provider=provider,
            run=run,
            trace_id=trace_id,
        )
        if response.warning_code:
            self._consecutive_model_errors += 1
            if self._consecutive_model_errors >= self.max_consecutive_model_errors:
                return self._finalize(
                    run, "partial", ["AGENT_MODEL_ERRORS_EXCEEDED"], trace_id
                ) and None
            return None
        self._consecutive_model_errors = 0
        return response

    def _build_request(self, run: AgentRun) -> AgentModelRequest:
        context = self._assembler.build(
            run, conversation_id=self._conversation_id(run)
        )
        context_text = _render_context(context)
        messages = [
            AgentModelMessage(role="system", content=SYSTEM_SECURITY_BOUNDARY),
            AgentModelMessage(role="user", content=context_text),
        ]
        if self._assistant_tool_calls:
            messages.append(
                AgentModelMessage(
                    role="assistant",
                    content=None,
                    tool_calls=tuple(self._assistant_tool_calls),
                )
            )
        if self._tool_results:
            messages = append_tool_results(messages, self._tool_results)
            self._tool_results = []
        if self._feedback:
            messages.append(
                AgentModelMessage(
                    role="user",
                    content="控制器反馈：" + "\n".join(self._feedback),
                )
            )
            self._feedback = []
        tools = tuple(
            AgentToolDefinition(
                name=descriptor.name,
                description=descriptor.description,
                input_schema=descriptor.input_schema,
            )
            for descriptor in self._registry.descriptors()
        )
        return AgentModelRequest(
            messages=tuple(messages),
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1500,
            metadata={
                "mode": self._status_value(run.mode),
                "iteration": run.iteration_count,
                "context_watermark": run.context_watermark,
            },
        )

    # ---------------------------------------------------------------- actions

    def _dispatch_action(self, run: AgentRun, action, trace_id: str) -> str:
        kind = action.kind
        if self._status_value(run.mode) == "baseline":
            if kind != ActionKind.FINAL_ANSWER:
                self._feedback.append(
                    "baseline 模式为显式策略工作流：模型仅可生成最终摘要，"
                    "工具与计划更新由 Controller 固定执行"
                )
                return "continue"
        if kind == ActionKind.TOOL_CALLS:
            return self._execute_tool_call(run, action.action, trace_id)
        if kind == ActionKind.PLAN_UPDATE:
            return self._apply_plan_update(run, action.action, trace_id)
        if kind == ActionKind.FINAL_ANSWER:
            return self._handle_final_answer(run, action.action.content, trace_id)
        if kind in {
            ActionKind.REQUEST_APPROVAL,
            ActionKind.ASK_USER,
        }:
            return "interrupted"
        return "continue"

    def _execute_tool_call(self, run: AgentRun, call, trace_id: str) -> str:
        repeat_key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
        self._same_tool_calls[repeat_key] = self._same_tool_calls.get(repeat_key, 0) + 1
        if self._same_tool_calls[repeat_key] > self.max_same_tool_same_args:
            return self._finalize(
                run, "partial", ["AGENT_REPEATED_TOOL_CALL"], trace_id
            )

        plan = self._latest_plan(run.id)
        if plan is None:
            return self._finalize(run, "failed", ["AGENT_PLAN_MISSING"], trace_id)
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key=f"loop_{run.iteration_count}_{call.call_id}",
            node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
            status=AgentPlanNodeStatus.READY.value,
            title=call.name,
            tool_name=call.name,
            input_json=call.arguments,
        )
        db.session.add(node)
        db.session.flush()
        step = AgentStepExecution(
            plan_node_id=node.id,
            run_id=run.id,
            attempt_number=1,
            worker_id="loop-engine",
            status="running",
        )
        db.session.add(step)
        db.session.flush()

        self._writer.emit(
            run,
            event_type=EVENT_TOOL_CALL_STARTED,
            item_id=call.call_id,
            parent_item_id=f"modelturn_{run.iteration_count}",
            payload={"name": call.name, "arguments_digest": _digest(call.arguments)},
            trace_id=trace_id,
        )
        result = self._tools.execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id=trace_id,
            input_payload=call.arguments,
        )
        self._writer.emit(
            run,
            event_type=EVENT_TOOL_CALL_COMPLETED,
            item_id=call.call_id,
            payload={
                "status": result.status,
                "error_code": result.error_code,
            },
            trace_id=trace_id,
        )
        self._writer.emit(
            run,
            event_type=EVENT_TOOL_RESULT_CREATED,
            item_id=f"result_{call.call_id}",
            parent_item_id=call.call_id,
            payload={
                "tool_name": call.name,
                "status": result.status,
                "summary": result.summary[:_MAX_TOOL_RESULT_SUMMARY_CHARS],
            },
            trace_id=trace_id,
        )
        db.session.commit()

        self._tool_results.append(
            {
                "call_id": call.call_id,
                "tool_name": call.name,
                "status": result.status,
                "summary": result.summary,
                "error_code": result.error_code,
            }
        )
        self._assistant_tool_calls.append(
            AgentModelToolCall(
                call_id=call.call_id,
                name=call.name,
                arguments=call.arguments,
            )
        )
        return "continue"

    def _apply_plan_update(self, run: AgentRun, action, trace_id: str) -> str:
        from app.services.security_agent.planning.plan_service import (
            PlanService,
            PlanServiceError,
        )

        plan = self._latest_plan(run.id)
        if plan is None:
            return self._finalize(run, "failed", ["AGENT_PLAN_MISSING"], trace_id)
        try:
            PlanService().apply_patch(
                run,
                plan,
                patch=action.patch,
                reason_code="model_plan_update",
                decision_type="model",
                decision_summary=str(action.patch)[:500],
                trace_id=trace_id,
            )
        except PlanServiceError as exc:
            self._feedback.append(f"计划更新被拒绝：{exc}")
        return "continue"

    def _handle_final_answer(self, run: AgentRun, content: str, trace_id: str) -> str:
        plan = self._latest_plan(run.id)
        evidence = {"observations_count": 0}
        from app.models.agent_items import AgentItem

        observations_count = (
            AgentItem.query.filter_by(
                run_id=run.id, item_type="observation"
            ).count()
            if plan is not None
            else 0
        )
        evidence["observations_count"] = observations_count
        verdict = self._evaluator.evaluate(
            run, plan, evidence=evidence, model_final=content
        )
        if verdict.accepted:
            return self._finalize_verdict(run, verdict, trace_id)
        self._feedback.append(
            "最终回答未被接受，缺失条件：" + "、".join(verdict.missing_requirements)
        )
        return "continue"

    # ---------------------------------------------------------------- baseline

    def _run_baseline_dag(self, run: AgentRun, trace_id: str) -> None:
        """baseline 显式"策略工作流"：Controller 固定执行强制 DAG。"""
        plan = self._latest_plan(run.id)
        if plan is None:
            return
        while True:
            schedule = self._scheduler.compute(plan)
            if not schedule.ready:
                for key in schedule.blocked:
                    node = _plan_node(plan, key)
                    if node is not None:
                        node.status = AgentPlanNodeStatus.BLOCKED.value
                db.session.commit()
                break
            for node in schedule.ready:
                if _status_value(node.status) == AgentPlanNodeStatus.SUCCEEDED.value:
                    continue
                step = AgentStepExecution(
                    plan_node_id=node.id,
                    run_id=run.id,
                    attempt_number=1,
                    worker_id="loop-engine-baseline",
                    status="running",
                )
                db.session.add(step)
                db.session.flush()
                node.status = AgentPlanNodeStatus.RUNNING.value
                db.session.commit()
                result = self._tools.execute(
                    run,
                    node,
                    step,
                    actor_id=run.created_by,
                    trace_id=trace_id,
                    input_payload=node.input_json or None,
                )
                node = db.session.get(AgentPlanNode, node.id)
                if node is None:
                    return
                node.status = (
                    AgentPlanNodeStatus.SUCCEEDED.value
                    if result.status == "succeeded"
                    else AgentPlanNodeStatus.FAILED.value
                )
                db.session.commit()
        self._baseline_done = True

    # ---------------------------------------------------------------- control / limits

    def _apply_control_inputs(self, run: AgentRun, trace_id: str) -> str:
        pending = self._controls.list_pending(run.id)
        for control in pending:
            input_type = control.input_type
            if input_type == "cancel":
                self._controls.apply(control, iteration=run.iteration_count or 0)
                self._state.transition(
                    run,
                    AgentRunStatus.CANCELED,
                    actor_id=run.created_by,
                    reason="控制输入：取消",
                    trace_id=trace_id,
                )
                return "canceled"
            if input_type == "pause":
                self._controls.apply(control, iteration=run.iteration_count or 0)
                self._state.transition(
                    run,
                    AgentRunStatus.PAUSED,
                    actor_id=run.created_by,
                    reason="控制输入：暂停",
                    trace_id=trace_id,
                )
                return "interrupted"
            if input_type == "user_message":
                self._controls.apply(control, iteration=run.iteration_count or 0)
                self._feedback.append(
                    f"用户新方向：{str((control.payload_json or {}).get('content') or '')[:400]}"
                )
                continue
            if input_type == "approval_result":
                self._controls.apply(control, iteration=run.iteration_count or 0)
                self._feedback.append(
                    f"审批结果：{(control.payload_json or {}).get('decision', '')}"
                )
                continue
            self._controls.apply(control, iteration=run.iteration_count or 0)
        return ""

    def _enforce_limits(self, run: AgentRun, trace_id: str) -> str:
        if (run.iteration_count or 0) >= self.max_iterations:
            return self._finalize(
                run, "partial", ["AGENT_ITERATION_LIMIT_REACHED"], trace_id
            )
        budget = budget_status(run)
        if budget["exhausted"]:
            return self._finalize(
                run, "partial", ["AGENT_BUDGET_EXHAUSTED"], trace_id
            )
        return ""

    # ---------------------------------------------------------------- finalize

    def _finalize(
        self, run: AgentRun, terminal_status: str, warning_codes: list[str], trace_id: str
    ) -> str:
        return self._finalize_verdict(
            run,
            CompletionVerdictLike(
                accepted=terminal_status in {"completed", "completed_with_warnings"},
                terminal_status=terminal_status,
                missing_requirements=(),
                warning_codes=tuple(warning_codes),
                completion_reason="engine limits",
            ),
            trace_id,
        )

    def _finalize_verdict(self, run: AgentRun, verdict, trace_id: str) -> str:
        from app.services.security_agent.loop.completion_evaluator import (
            CompletionVerdict,
        )

        if not isinstance(verdict, CompletionVerdict):
            verdict = CompletionVerdict(
                accepted=verdict.accepted,
                terminal_status=verdict.terminal_status,
                missing_requirements=verdict.missing_requirements,
                warning_codes=verdict.warning_codes,
                completion_reason=verdict.completion_reason,
            )
        try:
            self._state.transition(
                run,
                AgentRunStatus(verdict.terminal_status),
                actor_id=run.created_by,
                reason=verdict.completion_reason,
                trace_id=trace_id,
            )
        except Exception:
            db.session.rollback()
        warning_codes = list(dict.fromkeys(list(verdict.warning_codes)))
        if warning_codes:
            run.warning_codes = list(
                dict.fromkeys((run.warning_codes or []) + warning_codes)
            )
            self._writer.emit(
                run,
                event_type=EVENT_WARNING_RAISED,
                payload={"warning_codes": warning_codes},
                trace_id=trace_id,
            )
            db.session.commit()
        return verdict.terminal_status

    # ---------------------------------------------------------------- helpers

    def _latest_plan(self, run_id: int) -> AgentPlan | None:
        return (
            AgentPlan.query.filter_by(run_id=run_id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )

    def _conversation_id(self, run: AgentRun) -> int | None:
        from app.models.conversation import AgentTurn

        turn = (
            AgentTurn.query.filter_by(run_id=run.id)
            .order_by(AgentTurn.id.desc())
            .first()
        )
        return turn.conversation_id if turn is not None else None

    @staticmethod
    def _is_terminal(run: AgentRun) -> bool:
        return AgentStateMachine.is_terminal(
            _status_value(run.status)
        )

    @staticmethod
    def _status_value(value) -> str:
        return value.value if hasattr(value, "value") else str(value)


class EventServiceLike:
    """最小事件兼容（ToolExecutor 依赖 EventService.emit）。"""

    def emit(self, *args, **kwargs):
        from app.services.security_agent.event_service import EventService

        return EventService().emit(*args, **kwargs)


class CompletionVerdictLike:
    """_finalize 内部构造的轻量判决（与 CompletionVerdict 同构）。"""

    def __init__(self, *, accepted, terminal_status, missing_requirements, warning_codes, completion_reason):
        self.accepted = accepted
        self.terminal_status = terminal_status
        self.missing_requirements = missing_requirements
        self.warning_codes = warning_codes
        self.completion_reason = completion_reason


def _render_context(context: dict) -> str:
    parts = [
        f"目标：{context.get('goal') or ''}",
    ]
    plan = context.get("plan")
    if plan:
        nodes = ", ".join(
            f"{node['key']}({node['status']})" for node in plan.get("nodes", [])
        )
        parts.append(f"计划 v{plan.get('version')}: {nodes}")
    observations = context.get("recent_observations") or []
    if observations:
        parts.append(
            "最近观察：" + "; ".join(
                str((item.get("summary") or {}).get("summary") or item.get("summary") or "")[:200]
                for item in observations[:5]
            )
        )
    summary = context.get("conversation_summary") or {}
    if summary:
        parts.append(f"会话摘要 v{summary.get('summary_version')}")
    budget = context.get("budgets") or {}
    parts.append(
        f"预算：工具 {budget.get('max_tool_calls')} / 轮数上限 "
        f"{budget.get('max_llm_calls')}"
    )
    messages = context.get("recent_messages") or []
    for message in messages[-5:]:
        parts.append(f"{message.get('role')}: {str(message.get('content') or '')[:300]}")
    return "\n".join(parts)


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _plan_node(plan: AgentPlan, node_key: str) -> AgentPlanNode | None:
    for node in plan.nodes:
        if node.node_key == node_key:
            return node
    return None


def _digest(payload: dict) -> str:
    import hashlib

    raw = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
