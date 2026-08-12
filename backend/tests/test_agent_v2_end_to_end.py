# -*- coding: utf-8 -*-
"""T13 端到端测试：Scripted Provider + 真实 Registry/Executor 的多轮闭环。"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_items import AgentItem
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
    ProviderCapabilities,
)
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolResult,
)
from app.services.security_agent.tools.registry import ToolRegistry


class _ScriptedReviewProvider:
    """脚本化安全审查：工具A(鉴权映射) → 工具B(代码切片) → 工具C(深审) → 最终回答。"""

    provider_name = "e2e-scripted"
    model = "e2e-model"
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
        scripts = [
            AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-1",
                        name="auth_map_tool",
                        arguments={"limit": 20},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            ),
            AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-2",
                        name="slice_tool",
                        arguments={"file_path": "app/auth.py", "start_line": 1, "end_line": 80},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            ),
            AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-3",
                        name="deep_tool",
                        arguments={"focus": "鉴权链路越权"},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            ),
            AgentModelResponse(
                content="审查结论：鉴权链路存在水平越权风险，证据来自三次工具调用。",
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            ),
        ]
        return scripts[min(self._stage - 1, len(scripts) - 1)]


def _registry() -> ToolRegistry:
    registry = ToolRegistry()

    def make_handler(name):
        def handler(ctx):
            return ToolResult(
                status="succeeded",
                summary=f"{name} 完成：{ctx.input}",
                metrics={"calls": 1},
            )

        return handler

    for name in ("auth_map_tool", "slice_tool", "deep_tool"):
        registry.register(
            ToolDescriptor(
                name=name,
                version="1.0",
                category="test",
                description=name,
                input_schema={"type": "object", "properties": {}},
                risk_level="safe_read",
                timeout_seconds=5,
                idempotent=True,
            ),
            make_handler(name),
        )
    return registry


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


def test_v2_end_to_end_three_tool_rounds(app):
    run_id = _make_run(app)
    provider = _ScriptedReviewProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-e2e")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        assert run.tool_call_count == 3
        assert run.iteration_count == 4
        assert len(provider.requests) == 4
        # 每轮 Tool Result 真实进入下一轮
        for index in (1, 2, 3):
            messages = provider.requests[index].messages
            assert messages[-1].role == "tool", f"第 {index} 轮请求必须包含工具结果"
        # 最终回答以 assistant_message Item 固化
        assistant_items = AgentItem.query.filter_by(
            run_id=run_id, item_type="assistant_message"
        ).all()
        assert len(assistant_items) == 1
        assert "水平越权" in assistant_items[0].content_redacted
        # v2 事件顺序：tool started < tool result < assistant completed
        events = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        types = [event.event_type for event in events]
        assert "item.assistant_message.started" in types
        assert "item.assistant_message.completed" in types
        started = types.index("item.assistant_message.started")
        completed = types.index("item.assistant_message.completed")
        assert started < completed
        assert types.index("item.tool_call.started") < types.index("item.tool_result.created")


def test_v2_end_to_end_mandatory_baseline_failure_blocks_completion(app):
    """强制基线节点失败时，即使模型给出最终回答也不得 completed。"""
    run_id = _make_run(app)

    class _FailureProvider(_ScriptedReviewProvider):
        def generate_agent(self, request):
            self.requests.append(request)
            return AgentModelResponse(
                content="基线失败但给出结论",
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            )

    provider = _FailureProvider()
    with app.app_context():
        plan = (
            AgentPlan.query.filter_by(run_id=run_id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )
        node = next(node for node in plan.nodes if node.node_key == "baseline_scan")
        node.status = AgentPlanNodeStatus.FAILED.value
        db.session.commit()

        engine = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-e2e-fail")
        run = db.session.get(AgentRun, run_id)
        assert result == "failed"
        assert _status(run) == AgentRunStatus.FAILED.value


def _status(run) -> str:
    return run.status.value if hasattr(run.status, "value") else str(run.status)
