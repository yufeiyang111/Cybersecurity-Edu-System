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
import os

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
from app.services.security_agent.loop.lease_service import LeaseService
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
        leases=None,
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
        self._leases = leases or LeaseService()
        self._tools = ToolExecutor(self._registry, events or EventServiceLike())
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_consecutive_model_errors = max_consecutive_model_errors
        self.max_same_tool_same_args = _config_int(
            "AGENT_LOOP_MAX_SAME_TOOL_SAME_ARGS", max_same_tool_same_args
        )
        self._consecutive_model_errors = 0
        self._same_tool_calls: dict[str, int] = {}
        self._tool_results: list[dict] = []
        self._pending_calls: list[AgentModelToolCall] = []
        self._pending_assistant_message: AgentModelMessage | None = None
        self._last_reasoning_content: str | None = None
        self._feedback: list[str] = []
        self._baseline_done = False
        self._baseline_summary_attempts = 0

    def supported_actions(self) -> set[str]:
        return {kind.value for kind in ActionKind}

    # ---------------------------------------------------------------- loop

    def run_until_interrupt(self, run_id: int, trace_id: str) -> str:
        """推进到中断或终态；返回终态名或 interrupted。

        先原子获取 Lease（失败说明另一 Worker 在跑，立即让出，不重复执行）。
        """
        owner = f"loop-{os.getpid()}"
        lease_seconds = _config_int("AGENT_LOOP_LEASE_SECONDS", 60)
        if not self._leases.acquire(run_id, owner, lease_seconds=lease_seconds):
            return "interrupted"
        try:
            while True:
                run = db.session.get(AgentRun, run_id)
                if run is None:
                    return "failed"
                if self._is_terminal(run):
                    return self._status_value(run.status)
                self._leases.refresh(run_id, owner, lease_seconds=lease_seconds)
                try:
                    boot = self._bootstrap_run(run, trace_id)
                    if boot != "continue":
                        return boot
                    result = self.advance_once(run, trace_id)
                    if result != "continue":
                        return result
                except Exception as exc:
                    # 单轮异常不得让 worker 线程裸死：回滚后显式进入
                    # partial 并记录安全警告，由 watchdog/恢复入口接管。
                    logger.exception(
                        "agent loop iteration failed (run_id=%s, trace_id=%s, error_type=%s)",
                        run_id,
                        trace_id,
                        type(exc).__name__,
                    )
                    db.session.rollback()
                    run = db.session.get(AgentRun, run_id)
                    if run is None:
                        return "failed"
                    return self._finalize(
                        run, "partial", ["AGENT_LOOP_ITERATION_FAILED"], trace_id
                    )
        finally:
            try:
                self._leases.release(run_id, owner)
            except Exception:
                db.session.rollback()

    def _bootstrap_run(self, run: AgentRun, trace_id: str) -> str:
        """T08：v2 起点兼容——QUEUED 先前移到 PREPARING/EXECUTING_TOOLS，
        并确保存在已持久化的策略计划（与 v1 runner 的 _build_plan 对齐）。
        """
        status = self._status_value(run.status)
        if status == AgentRunStatus.QUEUED.value:
            try:
                self._state.transition(
                    run,
                    AgentRunStatus.PREPARING,
                    actor_id=run.created_by,
                    reason="v2 工作进程开始执行",
                    trace_id=trace_id,
                )
            except Exception:
                db.session.rollback()
                run = db.session.get(AgentRun, run.id)
                if run is None or self._status_value(run.status) != AgentRunStatus.QUEUED.value:
                    return "interrupted"
        if self._status_value(run.status) == AgentRunStatus.PREPARING.value:
            try:
                self._state.transition(
                    run,
                    AgentRunStatus.EXECUTING_TOOLS,
                    actor_id=run.created_by,
                    reason="计划就绪，开始执行节点",
                    trace_id=trace_id,
                )
            except Exception:
                db.session.rollback()
                run = db.session.get(AgentRun, run.id)
                if run is None or self._status_value(run.status) != AgentRunStatus.PREPARING.value:
                    return "interrupted"
        plan = self._latest_plan(run.id)
        if plan is None:
            from app.services.security_agent.event_service import EventService
            from app.services.security_agent.planner import PlanPlanner

            try:
                PlanPlanner(events=self._events or EventService()).generate_plan(
                    run, trace_id=trace_id
                )
            except Exception:
                logger.warning(
                    "plan bootstrap failed (run_id=%s, trace_id=%s)",
                    run.id,
                    trace_id,
                    exc_info=True,
                )
                db.session.rollback()
                return self._finalize(
                    run, "failed", ["AGENT_PLAN_MISSING"], trace_id
                )
        return "continue"

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

        if not self._baseline_done and not self._run_baseline_dag(run, trace_id):
            return "continue"

        request = self._build_request(run)
        response = self._next_model_turn(run, request, trace_id)
        if response == "interrupted":
            return "interrupted"
        if response is None:
            return "continue"

        try:
            action = response.to_action()
        except ContractValidationError as exc:
            tool_calls = response.tool_calls
            if tool_calls:
                if self._status_value(run.mode) == "baseline":
                    # baseline 为显式策略工作流：模型不得请求工具
                    self._baseline_summary_attempts += 1
                    if self._baseline_summary_attempts >= 2:
                        run.warning_codes = list(
                            dict.fromkeys(
                                (run.warning_codes or [])
                                + ["AGENT_BASELINE_MODEL_SUMMARY_FALLBACK"]
                            )
                        )
                        db.session.commit()
                        return self._handle_final_answer(
                            run, self._baseline_fallback_summary(run), trace_id
                        )
                    self._feedback.append(
                        "baseline 模式为显式策略工作流：模型仅可生成最终摘要"
                    )
                    return "continue"
                # 并行工具调用：按稳定顺序串行执行（数量受工具预算与
                # max_same_tool_same_args 约束），全部结果回填下一轮；
                # 存在依赖时由模型自行拆分轮次。
                run.iteration_count = (run.iteration_count or 0) + 1
                db.session.commit()
                for call in tool_calls:
                    terminal = self._execute_tool_call(run, call, trace_id)
                    if terminal != "continue":
                        return terminal
                self._flush_assistant_message()
                run = db.session.get(AgentRun, run.id)
                if run is None:
                    return "failed"
                run.context_watermark = run.last_event_sequence
                db.session.commit()
                return "continue"
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
        self._flush_assistant_message()

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
        if response.warning_code == "AGENT_APPROVAL_REQUIRED":
            return self._enter_awaiting_approval(run, trace_id)
        if response.warning_code:
            self._consecutive_model_errors += 1
            if self._consecutive_model_errors >= self.max_consecutive_model_errors:
                return self._finalize(
                    run, "partial", ["AGENT_MODEL_ERRORS_EXCEEDED"], trace_id
                ) and None
            return None
        self._consecutive_model_errors = 0
        self._last_reasoning_content = response.reasoning_content
        self._emit_reasoning_summary(run, response, trace_id)
        return response

    def _emit_reasoning_summary(
        self, run: AgentRun, response, trace_id: str
    ) -> None:
        """C-13/K-03：模型推理输出以受限 Reasoning Summary 形式实时下发。

        脱敏（redact_reasoning）→ 限长（REASONING_SUMMARY_MAX_CHARS）→
        标注 sensitive_level；完整原始思维链全文不落库、不进日志。
        非流式调用把完整脱敏结果作为单段 delta 发出，前端按 v2 事件累积。
        """
        from app.services.security_agent.loop.policy import REASONING_SUMMARY_MAX_CHARS
        from app.services.security_agent.timeline.contracts import (
            EVENT_REASONING_SUMMARY_STARTED,
            EVENT_REASONING_SUMMARY_DELTA,
        )
        from app.services.llm.redactor import redact_reasoning

        raw = response.reasoning_content
        if not isinstance(raw, str) or not raw.strip():
            return
        redacted = redact_reasoning(raw)
        if not redacted:
            return
        limited = redacted[:REASONING_SUMMARY_MAX_CHARS]
        sensitive_level = "internal" if redacted == limited else "truncated"
        iteration = run.iteration_count or 0
        item_id = f"reasoning_{iteration}"
        self._writer.emit(
            run,
            event_type=EVENT_REASONING_SUMMARY_STARTED,
            item_id=item_id,
            iteration=iteration,
            payload={
                "sensitive_level": sensitive_level,
                "max_chars": REASONING_SUMMARY_MAX_CHARS,
            },
            trace_id=trace_id,
        )
        self._writer.emit(
            run,
            event_type=EVENT_REASONING_SUMMARY_DELTA,
            item_id=item_id,
            parent_item_id=item_id,
            iteration=iteration,
            payload={
                "delta": limited,
                "sensitive_level": sensitive_level,
            },
            trace_id=trace_id,
        )
        db.session.commit()
    def _enter_awaiting_approval(self, run: AgentRun, trace_id: str) -> str:
        """审批中断：转入 AWAITING_APPROVAL 并让出 Worker，不占用轮询。"""
        try:
            self._state.transition(
                run,
                AgentRunStatus.AWAITING_APPROVAL,
                actor_id=run.created_by,
                reason="模型请求审批，等待人工决策",
                trace_id=trace_id,
            )
        except Exception:
            db.session.rollback()
        return "interrupted"

    def _build_request(self, run: AgentRun) -> AgentModelRequest:
        context = self._assembler.build(
            run, conversation_id=self._conversation_id(run)
        )
        context_text = _render_context(context)
        messages = [
            AgentModelMessage(role="system", content=SYSTEM_SECURITY_BOUNDARY),
            AgentModelMessage(role="user", content=context_text),
        ]
        if self._pending_assistant_message is not None:
            messages.append(self._pending_assistant_message)
            self._pending_assistant_message = None
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
                self._baseline_summary_attempts += 1
                if self._baseline_summary_attempts >= 2:
                    # baseline 是可靠降级路径：模型连续拒绝生成摘要时，
                    # 使用确定性摘要作为最终回答（不伪装模型分析）。
                    run.warning_codes = list(
                        dict.fromkeys(
                            (run.warning_codes or [])
                            + ["AGENT_BASELINE_MODEL_SUMMARY_FALLBACK"]
                        )
                    )
                    db.session.commit()
                    return self._handle_final_answer(
                        run, self._baseline_fallback_summary(run), trace_id
                    )
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
        # C-07 防死循环只针对非幂等/有副作用工具：safe_read 与敏感只读
        # 工具由 ToolExecutor 幂等去重（G-07），模型多轮复查是正常审查行为，
        # 不应被误判为死循环（真实验收：真实模型反复 get_authentication_map
        # 导致 run 47/49/53/54 全部 partial）。
        descriptor = next(
            (d for d in self._registry.descriptors() if d.name == call.name),
            None,
        )
        risk_level = getattr(descriptor, "risk_level", "safe_read")
        idempotent = getattr(descriptor, "idempotent", True)
        enforce_repeat_limit = not (idempotent and risk_level in {"safe_read", "sensitive_read"})
        if enforce_repeat_limit:
            self._same_tool_calls[repeat_key] = (
                self._same_tool_calls.get(repeat_key, 0) + 1
            )
            if self._same_tool_calls[repeat_key] > self.max_same_tool_same_args:
                return self._finalize(
                    run, "partial", ["AGENT_REPEATED_TOOL_CALL"], trace_id
                )

        plan = self._latest_plan(run.id)
        if plan is None:
            return self._finalize(run, "failed", ["AGENT_PLAN_MISSING"], trace_id)
        existing_keys = {
            node.node_key for node in plan.nodes
        }
        base_key = f"loop_{run.iteration_count}_{call.call_id}"
        node_key = base_key
        counter = 1
        while node_key in existing_keys:
            node_key = f"{base_key}_{counter}"
            counter += 1
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key=node_key,
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
        node = db.session.get(AgentPlanNode, node.id)
        if node is not None:
            node.status = (
                AgentPlanNodeStatus.SUCCEEDED.value
                if result.status == "succeeded"
                else AgentPlanNodeStatus.FAILED.value
            )
        step = db.session.get(AgentStepExecution, step.id)
        if step is not None:
            step.status = (
                "succeeded" if result.status == "succeeded" else "failed"
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
        self._pending_calls.append(
            AgentModelToolCall(
                call_id=call.call_id,
                name=call.name,
                arguments=call.arguments,
            )
        )
        return "continue"

    def _flush_assistant_message(self) -> None:
        """把本轮全部工具调用固化为一条 assistant 消息（协议要求每轮独立）。"""
        if not self._pending_calls:
            return
        self._pending_assistant_message = AgentModelMessage(
            role="assistant",
            content=None,
            tool_calls=tuple(self._pending_calls),
            reasoning_content=self._last_reasoning_content,
        )
        self._pending_calls = []
        self._last_reasoning_content = None

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
            self._persist_final_answer(run, content, trace_id)
            return self._finalize_verdict(run, verdict, trace_id)
        if verdict.terminal_status == "failed":
            # 强制节点失败：不可通过 feedback 修复，直接终态
            return self._finalize_verdict(run, verdict, trace_id)
        self._feedback.append(
            "最终回答未被接受，缺失条件：" + "、".join(verdict.missing_requirements)
        )
        return "continue"

    def _persist_final_answer(self, run: AgentRun, content: str, trace_id: str) -> None:
        """T10：最终回答以 assistant_message Item 固化（started → completed）。"""
        from app.services.security_agent.timeline.item_service import ItemService

        public_id = f"asst_final_{run.iteration_count}"
        service = ItemService()
        service.start(
            run,
            public_id=public_id,
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            iteration=run.iteration_count,
            sensitive_level="internal",
            trace_id=trace_id,
        )
        service.complete(
            run,
            public_id,
            content=content,
            summary_json={"mode": self._status_value(run.mode)},
            event_type="item.assistant_message.completed",
            trace_id=trace_id,
        )

    # ---------------------------------------------------------------- baseline

    def _run_baseline_dag(self, run: AgentRun, trace_id: str) -> bool:
        """Controller 固定执行强制 DAG（所有模式的第一阶段，spec F-06）。

        返回 True 表示 DAG 已执行（含无 plan 时标记完成）；False 表示没有
        plan 或执行中断，调用方应推进到下一轮重试。
        """
        plan = self._latest_plan(run.id)
        if plan is None:
            # bootstrap 阶段已确保 plan 存在；此处仅防御异常路径，
            # 标记 DAG 完成避免无限重试，由后续模型轮给出终态。
            self._baseline_done = True
            return True
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
                    return True
                node.status = (
                    AgentPlanNodeStatus.SUCCEEDED.value
                    if result.status == "succeeded"
                    else AgentPlanNodeStatus.FAILED.value
                )
                db.session.commit()
        self._baseline_done = True
        return True

    def _baseline_fallback_summary(self, run: AgentRun) -> str:
        """确定性基线摘要（模型拒绝生成摘要时的安全降级，不伪装模型分析）。"""
        plan = self._latest_plan(run.id)
        node_lines = []
        if plan is not None:
            for node in plan.nodes:
                node_lines.append(
                    f"{node.node_key}={_status_value(node.status)}"
                )
        return (
            "【确定性基线摘要（模型未生成最终摘要，已安全降级）】\n"
            f"运行模式：baseline（策略工作流）\n"
            f"强制节点状态：{'、'.join(node_lines) or '（无）'}\n"
            "结论由确定性工具证据产生，非模型分析。"
        )

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


def _config_int(key: str, default: int) -> int:
    from flask import current_app

    if current_app is None:
        return default
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default


def _plan_node(plan: AgentPlan, node_key: str) -> AgentPlanNode | None:
    for node in plan.nodes:
        if node.node_key == node_key:
            return node
    return None


def _digest(payload: dict) -> str:
    import hashlib

    raw = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
