# -*- coding: utf-8 -*-
"""T08 纵向切片测试：三轮交错 Model/Tool/Observation → Final Answer。"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.loop.engine import AgentLoopEngine
from app.services.security_agent.model.contracts import (
    AgentModelRequest,
    AgentModelResponse,
    AgentModelToolCall,
    AgentToolDefinition,
    ProviderCapabilities,
)
from app.services.security_agent.tools.registry import ToolRegistry


class _VerticalProvider:
    """脚本化三阶段：工具A → 工具B → 最终回答。"""

    provider_name = "vertical"
    model = "vertical-model"
    model_version = "1"
    provider_config_id = None

    def __init__(self) -> None:
        self.requests = []
        self._stage = 0

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True)

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        self._stage += 1
        if self._stage == 1:
            return AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-a",
                        name="tool_a",
                        arguments={"query": "auth"},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            )
        if self._stage == 2:
            return AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-b",
                        name="tool_b",
                        arguments={"file": "app/auth.py"},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            )
        return AgentModelResponse(
            content="审查完成：鉴权链路存在水平越权风险，证据见工具结果。",
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
        )


def _make_run(app, *, mode="hybrid"):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="重点检查鉴权与越权",
            mode=mode,
            status=AgentRunStatus.EXECUTING_TOOLS.value,
            max_iterations=20,
            max_tool_calls=30,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="重点检查鉴权与越权",
        )
        db.session.add(plan)
        db.session.flush()
        for key, node_type in (
            ("inventory", AgentPlanNodeType.INVENTORY.value),
            ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value),
            ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value),
            ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value),
        ):
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=key,
                    node_type=node_type,
                    status=AgentPlanNodeStatus.SUCCEEDED.value,
                    title=key,
                    tool_name=key,
                )
            )
        db.session.commit()
        return run.id


def _registry() -> ToolRegistry:
    from app.services.security_agent.tools.contracts import (
        ToolDescriptor,
        ToolResult,
    )

    registry = ToolRegistry()

    def make_handler(name):
        def handler(ctx):
            return ToolResult(
                status="succeeded",
                summary=f"{name} 完成：{ctx.input}",
                metrics={"calls": 1},
            )

        return handler

    registry.register(
        ToolDescriptor(
            name="tool_a",
            version="1.0",
            category="test",
            description="工具A",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=5,
            idempotent=True,
        ),
        make_handler("tool_a"),
    )
    registry.register(
        ToolDescriptor(
            name="tool_b",
            version="1.0",
            category="test",
            description="工具B",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=5,
            idempotent=True,
        ),
        make_handler("tool_b"),
    )
    return registry


def test_vertical_slice_three_interleaved_rounds(app):
    run_id = _make_run(app)
    provider = _VerticalProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-vertical")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        assert len(provider.requests) == 3
        # 第二轮必须包含第一轮 Tool A 的真实结果
        assert provider.requests[1].messages[-1].role == "tool"
        assert "tool_a 完成" in provider.requests[1].messages[-1].content
        # 第三轮必须包含第二轮 Tool B 的真实结果
        assert provider.requests[2].messages[-1].role == "tool"
        assert "tool_b 完成" in provider.requests[2].messages[-1].content
        assert run.tool_call_count == 2
        assert run.iteration_count == 3


def test_vertical_slice_events_in_order(app):
    run_id = _make_run(app)
    provider = _VerticalProvider()
    with app.app_context():
        AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        ).run_until_interrupt(run_id, "t-events")
        events = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        types = [event.event_type for event in events]
        assert "item.tool_call.started" in types
        assert "item.tool_result.created" in types
        tool_start = types.index("item.tool_call.started")
        tool_result = types.index("item.tool_result.created")
        assert tool_start < tool_result, "Tool Result 必须晚于 Tool Call"


class _BaselineSummaryProvider:
    """baseline 专用：模型只输出最终摘要。"""

    provider_name = "baseline-summary"
    model = "m"
    model_version = "1"
    provider_config_id = None

    def __init__(self) -> None:
        self.requests = []

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True)

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        return AgentModelResponse(
            content="基线扫描完成：确定性证据摘要，无模型自主动作。",
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
        )


def test_baseline_mode_runs_dag_once_and_single_summary(app):
    """baseline 不伪装自治：强制 DAG 确定性执行，模型只做一次安全摘要。"""
    run_id = _make_run(app, mode="baseline")
    provider = _BaselineSummaryProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-baseline")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        assert run.mode == "baseline"
        assert len(provider.requests) == 1, "baseline 模式模型只允许一次最终摘要"
        assert provider.requests[0].messages[0].role == "system"


def test_baseline_model_tool_calls_are_rejected(app):
    """baseline 模式模型请求工具调用会被 Controller 拒绝并反馈。"""
    run_id = _make_run(app, mode="baseline")

    class _ToolRequestingProvider(_BaselineSummaryProvider):
        def __init__(self) -> None:
            super().__init__()
            self.tool_requested = False

        def generate_agent(self, request):
            self.requests.append(request)
            if not self.tool_requested:
                self.tool_requested = True
                return AgentModelResponse(
                    content=None,
                    tool_calls=(
                        AgentModelToolCall(
                            call_id="call-x",
                            name="tool_a",
                            arguments={},
                        ),
                    ),
                    finish_reason="tool_calls",
                    provider_name=self.provider_name,
                    model=self.model,
                )
            return AgentModelResponse(
                content="基线完成摘要",
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            )

    provider = _ToolRequestingProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-baseline-reject")
        assert result == "completed"
        assert provider.tool_requested is True
        assert (
            AgentRun.query.get(run_id).tool_call_count == 0
        ), "baseline 模型请求的工具调用不得执行"


def test_baseline_falls_back_to_deterministic_summary(app):
    """模型持续拒绝生成摘要时，baseline 安全降级为确定性摘要并终态完成。"""
    run_id = _make_run(app, mode="baseline")

    class _StubbornProvider(_BaselineSummaryProvider):
        def generate_agent(self, request):
            self.requests.append(request)
            return AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id=f"call-{len(self.requests)}",
                        name="tool_a",
                        arguments={},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            )

    provider = _StubbornProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-baseline-fallback")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed_with_warnings"
        assert "AGENT_BASELINE_MODEL_SUMMARY_FALLBACK" in (run.warning_codes or [])
        assert run.tool_call_count == 0, "降级路径不得执行任何工具"
        from app.models.agent_items import AgentItem

        assistant = AgentItem.query.filter_by(
            run_id=run_id, item_type="assistant_message"
        ).all()
        assert len(assistant) == 1
        assert "确定性基线摘要" in assistant[0].content_redacted


def test_parallel_tool_calls_executed_serially(app):
    """模型返回多个并行工具调用时按稳定顺序串行执行并全部回填。"""
    run_id = _make_run(app)

    class _ParallelProvider(_VerticalProvider):
        def generate_agent(self, request):
            self.requests.append(request)
            self._stage += 1
            if self._stage == 1:
                return AgentModelResponse(
                    content=None,
                    tool_calls=(
                        AgentModelToolCall(call_id="p-1", name="tool_a", arguments={}),
                        AgentModelToolCall(call_id="p-2", name="tool_b", arguments={}),
                        AgentModelToolCall(call_id="p-3", name="tool_a", arguments={}),
                    ),
                    finish_reason="tool_calls",
                    provider_name=self.provider_name,
                    model=self.model,
                )
            return AgentModelResponse(
                content="并行调用完成",
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            )

    provider = _ParallelProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-parallel")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        assert run.tool_call_count == 3
        assert len(provider.requests) == 2
        second = provider.requests[1]
        tool_roles = [message.role for message in second.messages]
        assert tool_roles.count("tool") == 3, "3 个并行调用结果全部回填"
        assistant_messages = [
            message
            for message in second.messages
            if message.role == "assistant"
        ]
        assert len(assistant_messages) == 1
        assert len(assistant_messages[0].tool_calls) == 3


def test_queued_run_without_plan_bootstraps_plan(app, monkeypatch):
    """真实起点（QUEUED + 无 plan）必须 bootstrap 策略计划后才进入模型轮；
    否则 QUEUED→FAILED 被状态机拒绝，run 会永久卡在 QUEUED（真实验收复现）。"""
    from app.services.security_agent.planner import PlanPlanner

    run_id = _make_run(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        run.status = AgentRunStatus.QUEUED.value
        db.session.query(AgentPlanNode).filter(AgentPlanNode.plan_id.in_(
            db.session.query(AgentPlan.id).filter_by(run_id=run_id)
        )).delete(synchronize_session=False)
        db.session.query(AgentPlan).filter_by(run_id=run_id).delete()
        db.session.commit()

        def _fake_generate_plan(self, run, *, trace_id):
            plan = AgentPlan(
                run_id=run.id,
                plan_version=run.plan_version + 1,
                planner_source="rule_based_policy",
                objective=run.goal_text,
            )
            db.session.add(plan)
            db.session.flush()
            db.session.add_all(
                [
                    AgentPlanNode(
                        plan_id=plan.id,
                        node_key=key,
                        node_type=node_type,
                        status=AgentPlanNodeStatus.SUCCEEDED.value,
                        title=key,
                        tool_name=key,
                    )
                    for key, node_type in (
                        ("inventory", AgentPlanNodeType.INVENTORY.value),
                        ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value),
                        ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value),
                        ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value),
                    )
                ]
            )
            run.plan_version = plan.plan_version
            db.session.commit()
            return plan

        monkeypatch.setattr(PlanPlanner, "generate_plan", _fake_generate_plan)
        provider = _VerticalProvider()
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-bootstrap")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed", f"QUEUED 起点应 bootstrap 后完成，实际 {result}"
        assert run.status == AgentRunStatus.COMPLETED.value
        assert run.tool_call_count == 2
        assert len(provider.requests) == 3
        events = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        types = [event.event_type for event in events]
        assert AgentPlan.query.filter_by(run_id=run_id).first() is not None, \
            "bootstrap 必须持久化策略计划"
        assert "item.tool_call.started" in types


def test_hybrid_mode_controller_executes_mandatory_dag_first(app, monkeypatch):
    """F-06：hybrid 模式第一阶段必须由 Controller 执行强制基线 DAG，
    模型轮不得跳过/伪造强制节点成功（真实验收复现：此前模型绕过 DAG
    直接调工具，完成度显示 0/15 节点）。"""
    from app.services.security_agent.planner import PlanPlanner

    run_id = _make_run(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        run.status = AgentRunStatus.QUEUED.value
        db.session.query(AgentPlanNode).filter(AgentPlanNode.plan_id.in_(
            db.session.query(AgentPlan.id).filter_by(run_id=run_id)
        )).delete(synchronize_session=False)
        db.session.query(AgentPlan).filter_by(run_id=run_id).delete()
        db.session.commit()

        def _fake_generate_plan(self, run, *, trace_id):
            plan = AgentPlan(
                run_id=run.id,
                plan_version=run.plan_version + 1,
                planner_source="rule_based_policy",
                objective=run.goal_text,
            )
            db.session.add(plan)
            db.session.flush()
            db.session.add_all(
                [
                    AgentPlanNode(
                        plan_id=plan.id,
                        node_key=key,
                        node_type=node_type,
                        status=AgentPlanNodeStatus.READY.value,
                        title=key,
                        tool_name=tool_name,
                    )
                    for key, node_type, tool_name in (
                        ("inventory", AgentPlanNodeType.INVENTORY.value, "tool_a"),
                        ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value, "tool_b"),
                        ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value, "tool_a"),
                        ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value, "tool_b"),
                    )
                ]
            )
            run.plan_version = plan.plan_version
            db.session.commit()
            return plan

        monkeypatch.setattr(PlanPlanner, "generate_plan", _fake_generate_plan)
        provider = _VerticalProvider()
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-hybrid-dag")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        plan = AgentPlan.query.filter_by(run_id=run_id).order_by(
            AgentPlan.plan_version.desc()
        ).first()
        assert plan is not None
        node_statuses = {
            node.node_key: node.status for node in plan.nodes
        }
        succeeded = AgentPlanNodeStatus.SUCCEEDED.value
        for key in ("inventory", "baseline_scan", "coverage_analysis", "risk_ranking"):
            assert node_statuses[key] == succeeded, \
                f"强制节点 {key} 必须由 Controller 执行成功"
        first_tool_event = (
            AgentEvent.query.filter_by(run_id=run_id, event_type="tool.started")
            .order_by(AgentEvent.sequence.asc())
            .first()
        )
        assert first_tool_event is not None
        payload = first_tool_event.payload_json or first_tool_event.payload or {}
        assert payload.get("node_key") == "inventory", \
            "DAG 阶段第一个工具必须是强制节点 inventory（由 Controller 调度）"


def test_model_loop_nodes_marked_succeeded(app, monkeypatch):
    """模型轮工具执行成功后，其 loop_* 节点必须标记 SUCCEEDED（真实验收发现：
    此前节点永远停在 READY，导致 UI 完成度错误显示 31%、评估器误判缺失）。"""
    from app.services.security_agent.planner import PlanPlanner

    run_id = _make_run(app)
    with app.app_context():
        db.session.query(AgentPlanNode).filter(AgentPlanNode.plan_id.in_(
            db.session.query(AgentPlan.id).filter_by(run_id=run_id)
        )).delete(synchronize_session=False)
        db.session.query(AgentPlan).filter_by(run_id=run_id).delete()
        db.session.commit()

        def _fake_generate_plan(self, run, *, trace_id):
            plan = AgentPlan(
                run_id=run.id,
                plan_version=run.plan_version + 1,
                planner_source="rule_based_policy",
                objective=run.goal_text,
            )
            db.session.add(plan)
            db.session.flush()
            db.session.add_all(
                [
                    AgentPlanNode(
                        plan_id=plan.id,
                        node_key=key,
                        node_type=node_type,
                        status=AgentPlanNodeStatus.SUCCEEDED.value,
                        title=key,
                        tool_name=tool_name,
                    )
                    for key, node_type, tool_name in (
                        ("inventory", AgentPlanNodeType.INVENTORY.value, "tool_a"),
                        ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value, "tool_b"),
                        ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value, "tool_a"),
                        ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value, "tool_b"),
                    )
                ]
            )
            run.plan_version = plan.plan_version
            db.session.commit()
            return plan

        monkeypatch.setattr(PlanPlanner, "generate_plan", _fake_generate_plan)
        provider = _VerticalProvider()
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-model-nodes")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        plan = AgentPlan.query.filter_by(run_id=run_id).order_by(
            AgentPlan.plan_version.desc()
        ).first()
        assert plan is not None
        loop_nodes = [node for node in plan.nodes if node.node_key.startswith("loop_")]
        assert loop_nodes, "模型轮必须创建 loop_* 节点"
        succeeded = AgentPlanNodeStatus.SUCCEEDED.value
        for node in loop_nodes:
            assert node.status == succeeded, \
                f"模型轮节点 {node.node_key} 执行成功但状态仍是 {node.status}"


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def test_multiround_parallel_calls_do_not_collide_node_keys(app):
    """多轮并行工具调用必须递增 iteration_count，否则 node_key（loop_{iter}_{call_id}）
    跨轮相同导致唯一约束冲突、worker 线程裸死、run 永久卡死（run 48/50 真实验收复现）。"""
    run_id = _make_run(app)

    class _MultiRoundParallelProvider(_VerticalProvider):
        def generate_agent(self, request):
            self.requests.append(request)
            self._stage += 1
            if self._stage <= 3:
                return AgentModelResponse(
                    content=None,
                    tool_calls=(
                        AgentModelToolCall(
                            call_id=f"same-id-{self._stage}",
                            name="tool_a",
                            arguments={"round": self._stage},
                        ),
                        AgentModelToolCall(
                            call_id=f"same-id-{self._stage}",
                            name="tool_b",
                            arguments={"round": self._stage},
                        ),
                    ),
                    finish_reason="tool_calls",
                    provider_name=self.provider_name,
                    model=self.model,
                )
            return AgentModelResponse(
                content="审查完成",
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            )

    provider = _MultiRoundParallelProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-multiround-parallel")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed", f"多轮并行调用应正常完成，实际 {result}"
        assert run.tool_call_count == 6
        plan = AgentPlan.query.filter_by(run_id=run_id).order_by(
            AgentPlan.plan_version.desc()
        ).first()
        keys = [node.node_key for node in plan.nodes if node.node_key.startswith("loop_")]
        assert len(keys) == len(set(keys)), f"loop_* 节点 key 必须唯一，实际 {keys}"
        assert run.iteration_count >= 3, \
            f"三组并行调用应递增至少 3 次 iteration，实际 {run.iteration_count}"


def test_safe_read_repeats_do_not_trigger_dead_loop_guard(app, monkeypatch):
    """C-07 防死循环只针对非幂等/有副作用工具：safe_read 工具多轮复查
    是真实模型的正常行为，不应误判为死循环（run 47/49/53/54 真实验收复现）。"""
    from app.services.security_agent.planner import PlanPlanner

    run_id = _make_run(app)
    with app.app_context():
        db.session.query(AgentPlanNode).filter(AgentPlanNode.plan_id.in_(
            db.session.query(AgentPlan.id).filter_by(run_id=run_id)
        )).delete(synchronize_session=False)
        db.session.query(AgentPlan).filter_by(run_id=run_id).delete()
        db.session.commit()

        def _fake_generate_plan(self, run, *, trace_id):
            plan = AgentPlan(
                run_id=run.id,
                plan_version=run.plan_version + 1,
                planner_source="rule_based_policy",
                objective=run.goal_text,
            )
            db.session.add(plan)
            db.session.flush()
            db.session.add_all(
                [
                    AgentPlanNode(
                        plan_id=plan.id,
                        node_key=key,
                        node_type=node_type,
                        status=AgentPlanNodeStatus.SUCCEEDED.value,
                        title=key,
                        tool_name=tool_name,
                    )
                    for key, node_type, tool_name in (
                        ("inventory", AgentPlanNodeType.INVENTORY.value, "tool_a"),
                        ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value, "tool_b"),
                        ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value, "tool_a"),
                        ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value, "tool_b"),
                    )
                ]
            )
            run.plan_version = plan.plan_version
            db.session.commit()
            return plan

        monkeypatch.setattr(PlanPlanner, "generate_plan", _fake_generate_plan)

        class _RepeatedSafeReadProvider(_VerticalProvider):
            def generate_agent(self, request):
                self.requests.append(request)
                self._stage += 1
                if self._stage <= 5:
                    return AgentModelResponse(
                        content=None,
                        tool_calls=(
                            AgentModelToolCall(
                                call_id=f"c{self._stage}", name="tool_a", arguments={}
                            ),
                        ),
                        finish_reason="tool_calls",
                        provider_name=self.provider_name,
                        model=self.model,
                    )
                return AgentModelResponse(
                    content="审查完成",
                    tool_calls=(),
                    finish_reason="stop",
                    provider_name=self.provider_name,
                    model=self.model,
                )

        provider = _RepeatedSafeReadProvider()
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-safe-read-repeats")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed", \
            f"safe_read 工具重复调用不应触发死循环保护，实际 {result}"
        assert "AGENT_REPEATED_TOOL_CALL" not in (run.warning_codes or [])


def test_non_idempotent_repeats_still_trigger_dead_loop_guard(app, monkeypatch):
    """C-07 死循环保护必须保留：非幂等/有副作用工具重复调用仍触发拦截。"""
    from app.services.security_agent.planner import PlanPlanner
    from app.services.security_agent.tools.contracts import (
        ToolDescriptor,
        ToolResult,
    )

    run_id = _make_run(app)
    with app.app_context():
        db.session.query(AgentPlanNode).filter(AgentPlanNode.plan_id.in_(
            db.session.query(AgentPlan.id).filter_by(run_id=run_id)
        )).delete(synchronize_session=False)
        db.session.query(AgentPlan).filter_by(run_id=run_id).delete()
        db.session.commit()

        def _fake_generate_plan(self, run, *, trace_id):
            plan = AgentPlan(
                run_id=run.id,
                plan_version=run.plan_version + 1,
                planner_source="rule_based_policy",
                objective=run.goal_text,
            )
            db.session.add(plan)
            db.session.flush()
            db.session.add_all(
                [
                    AgentPlanNode(
                        plan_id=plan.id,
                        node_key=key,
                        node_type=node_type,
                        status=AgentPlanNodeStatus.SUCCEEDED.value,
                        title=key,
                        tool_name=tool_name,
                    )
                    for key, node_type, tool_name in (
                        ("inventory", AgentPlanNodeType.INVENTORY.value, "tool_a"),
                        ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value, "tool_b"),
                        ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value, "tool_a"),
                        ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value, "tool_b"),
                    )
                ]
            )
            run.plan_version = plan.plan_version
            db.session.commit()
            return plan

        monkeypatch.setattr(PlanPlanner, "generate_plan", _fake_generate_plan)

        registry = _registry()
        registry.register(
            ToolDescriptor(
                name="state_changer",
                version="1.0",
                category="test",
                description="有副作用工具",
                input_schema={"type": "object", "properties": {}},
                risk_level="state_changing",
                timeout_seconds=5,
                idempotent=False,
            ),
            lambda ctx: ToolResult(status="succeeded", summary="changed"),
        )

        class _RepeatedStateChangingProvider(_VerticalProvider):
            def generate_agent(self, request):
                self.requests.append(request)
                self._stage += 1
                if self._stage <= 4:
                    return AgentModelResponse(
                        content=None,
                        tool_calls=(
                            AgentModelToolCall(
                                call_id=f"s{self._stage}",
                                name="state_changer",
                                arguments={},
                            ),
                        ),
                        finish_reason="tool_calls",
                        provider_name=self.provider_name,
                        model=self.model,
                    )
                return AgentModelResponse(
                    content="审查完成",
                    tool_calls=(),
                    finish_reason="stop",
                    provider_name=self.provider_name,
                    model=self.model,
                )

        provider = _RepeatedStateChangingProvider()
        engine = AgentLoopEngine(
            provider=provider,
            registry=registry,
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-state-changer-repeats")
        run = db.session.get(AgentRun, run_id)
        assert result == "partial", \
            f"非幂等工具重复调用必须触发死循环保护，实际 {result}"
        assert "AGENT_REPEATED_TOOL_CALL" in (run.warning_codes or [])


def test_v2_reasoning_summary_events_emitted_redacted(app):
    """C-13：v2 模型轮必须发 item.reasoning_summary.* 受限摘要事件（脱敏、
    限长、sensitive_level），前端思考过程由此驱动（真实验收发现 v2 从不发
    推理事件导致前端无思考过程）。"""
    run_id = _make_run(app)

    class _ReasoningProvider(_VerticalProvider):
        def generate_agent(self, request):
            self.requests.append(request)
            self._stage += 1
            if self._stage == 1:
                return AgentModelResponse(
                    content="继续分析认证链路",
                    reasoning_content=(
                        "先分析认证链路，发现硬编码密钥 sk-abcdefghijklmnopqrstuvw "
                        "在 src/index.ts 第 1 行，需要脱敏展示。"
                    ),
                    tool_calls=(),
                    finish_reason="stop",
                    provider_name=self.provider_name,
                    model=self.model,
                )
            return AgentModelResponse(
                content="审查完成",
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            )

    provider = _ReasoningProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-reasoning-events")
        assert result == "completed"
        events = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        reasoning_events = [
            event for event in events
            if event.event_type.startswith("item.reasoning_summary.")
        ]
        assert reasoning_events, "v2 模型轮必须产生 item.reasoning_summary.* 事件"
        started = [e for e in reasoning_events if e.event_type == "item.reasoning_summary.started"]
        deltas = [e for e in reasoning_events if e.event_type == "item.reasoning_summary.delta"]
        assert started, "必须有 reasoning_summary.started 事件"
        assert deltas, "必须有 reasoning_summary.delta 事件"
        serialized = ""
        for event in reasoning_events:
            payload = event.payload_json or event.payload or {}
            assert payload.get("sensitive_level"), "推理摘要事件必须标注 sensitive_level"
            serialized += str(payload)
        assert "sk-abcdefghijklmnopqrstuvw" not in serialized, \
            "推理摘要必须脱敏，不得泄露密钥"
        assert "硬编码密钥" in serialized or "REDACTED" in serialized or "sk-" not in serialized


def test_persist_final_answer_unique_public_id(app):
    """baseline 降级/异常重试可能多次固化最终回答，public_id 必须唯一
    （真实验收 run 58：固定 asst_final_{iteration} 撞 agent_items 唯一约束）。"""
    from app.models.agent_items import AgentItem
    from app.services.security_agent.loop.engine import AgentLoopEngine

    run_id = _make_run(app)
    with app.app_context():
        engine = AgentLoopEngine(events=EventService())
        run = db.session.get(AgentRun, run_id)
        engine._persist_final_answer(run, "第一次摘要", "t-persist-1")
        db.session.commit()
        engine._persist_final_answer(run, "第二次摘要（重试）", "t-persist-2")
        db.session.commit()
        items = (
            AgentItem.query.filter_by(run_id=run_id, item_type="assistant_message")
            .all()
        )
        assert len(items) == 2, "两次固化必须产生两条独立 assistant_message Item"
        public_ids = {item.public_id for item in items}
        assert len(public_ids) == 2, "public_id 必须唯一"


def test_streaming_model_turn_emits_reasoning_delta_and_tool_calls(app):
    """流式模型轮必须实时下发脱敏推理 delta 并正确累积工具调用
    （真实 provider 的 <think> 思考块只在流式增量中完整可见）。"""
    from app.services.security_agent.model.contracts import (
        AgentModelStreamEvent,
        AgentStreamEventType,
        ProviderCapabilities,
    )

    run_id = _make_run(app)

    class _StreamProvider(_VerticalProvider):
        provider_name = "stream"
        model = "stream-model"

        def agent_capabilities(self):
            return ProviderCapabilities(
                supports_native_tools=True, supports_streaming=True
            )

        def generate_agent_stream(self, request):
            self._stage += 1
            if self._stage == 1:
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.REASONING_SUMMARY_DELTA.value,
                    item_id="reasoning",
                    delta="先分析认证链路，发现 sk-abcdefghijklmnopqrstuvw 密钥",
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.REASONING_SUMMARY_DELTA.value,
                    item_id="reasoning",
                    delta="，继续追调用链。",
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.TOOL_CALL_STARTED.value,
                    call_id="call-1",
                    payload={"name": "tool_a"},
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.TOOL_CALL_COMPLETED.value,
                    call_id="call-1",
                    payload={"name": "tool_a", "arguments": {"query": "auth"}},
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.COMPLETED.value
                )
                return
            yield AgentModelStreamEvent(
                event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                item_id="assistant",
                delta="审查完成：认证链路无越权风险。",
            )
            yield AgentModelStreamEvent(
                event_type=AgentStreamEventType.COMPLETED.value
            )

        def generate_agent(self, request):
            return AgentModelResponse(
                content="兜底", tool_calls=(), finish_reason="stop",
                provider_name=self.provider_name, model=self.model,
            )

    provider = _StreamProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-stream-model")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed", f"流式模型轮应正常完成，实际 {result}"
        assert run.tool_call_count == 1
        events = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        reasoning = [
            e for e in events
            if e.event_type.startswith("item.reasoning_summary.")
        ]
        assert reasoning, "流式模型轮必须产生推理摘要事件"
        serialized = "".join(
            str(e.payload_json or e.payload or {}) for e in reasoning
        )
        assert "sk-abcdefghijklmnopqrstuvw" not in serialized, \
            "推理摘要必须脱敏"
        assert "认证链路" in serialized or "REDACTED" in serialized
        assert any(
            e.event_type == "item.tool_call.started" for e in events
        ), "工具调用事件必须产生"


def test_streaming_tool_round_with_prefix_text_does_not_conflict(app):
    """流式工具轮：content 前缀文本（think 块外）与 tool_calls 并存时，
    文本必须丢弃、只执行工具（真实验收 run 72：两者并存触发
    ContractValidationError 导致 AGENT_LOOP_ITERATION_FAILED）。"""
    from app.services.security_agent.model.contracts import (
        AgentModelStreamEvent,
        AgentStreamEventType,
        ProviderCapabilities,
    )

    run_id = _make_run(app)

    class _PrefixTextProvider(_VerticalProvider):
        provider_name = "stream-prefix"
        model = "m"

        def agent_capabilities(self):
            return ProviderCapabilities(
                supports_native_tools=True, supports_streaming=True
            )

        def generate_agent_stream(self, request):
            self._stage += 1
            if self._stage == 1:
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.REASONING_SUMMARY_DELTA.value,
                    item_id="reasoning",
                    delta="先分析认证链路",
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                    item_id="assistant",
                    delta="好的，我来检查认证链路",
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.TOOL_CALL_STARTED.value,
                    call_id="c1",
                    payload={"name": "tool_a"},
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.TOOL_CALL_COMPLETED.value,
                    call_id="c1",
                    payload={"name": "tool_a", "arguments": {"query": "auth"}},
                )
                yield AgentModelStreamEvent(
                    event_type=AgentStreamEventType.COMPLETED.value
                )
                return
            yield AgentModelStreamEvent(
                event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                item_id="assistant",
                delta="审查完成",
            )
            yield AgentModelStreamEvent(
                event_type=AgentStreamEventType.COMPLETED.value
            )

        def generate_agent(self, request):
            return AgentModelResponse(
                content="兜底", tool_calls=(), finish_reason="stop",
                provider_name=self.provider_name, model=self.model,
            )

    provider = _PrefixTextProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-stream-prefix")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed", f"带前缀文本的工具轮应正常完成，实际 {result}"
        assert run.tool_call_count == 1, "前缀文本不得阻止工具执行"
