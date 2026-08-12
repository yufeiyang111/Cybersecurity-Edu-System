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
