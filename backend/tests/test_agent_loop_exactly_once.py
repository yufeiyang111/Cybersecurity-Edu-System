# -*- coding: utf-8 -*-
"""T09 恰好一次测试：重复 dispatch 不重复工具/事件，终态 Run 幂等。"""
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
    ProviderCapabilities,
)
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolResult,
)
from app.services.security_agent.tools.registry import ToolRegistry


class _OneToolProvider:
    """先调用一次工具，再给出最终回答。"""

    provider_name = "one-tool"
    model = "m"
    model_version = "1"
    provider_config_id = None

    def __init__(self) -> None:
        self.requests = []

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True)

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-1",
                        name="count_tool",
                        arguments={},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            )
        return AgentModelResponse(
            content="完成",
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
        )


def _make_run(app):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="恰好一次测试",
            mode="hybrid",
            status=AgentRunStatus.EXECUTING_TOOLS.value,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="恰好一次测试",
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
    registry = ToolRegistry()
    calls = {"count": 0}

    def handler(ctx):
        calls["count"] += 1
        return ToolResult(status="succeeded", summary=f"count={calls['count']}")

    registry.register(
        ToolDescriptor(
            name="count_tool",
            version="1.0",
            category="test",
            description="count",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=5,
            idempotent=True,
        ),
        handler,
    )
    return registry, calls


def test_duplicate_dispatch_does_not_repeat_tool_or_events(app):
    run_id = _make_run(app)
    provider = _OneToolProvider()
    registry, calls = _registry()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=registry,
            events=EventService(),
        )
        first = engine.run_until_interrupt(run_id, "t-first")
        assert first == "completed"
        assert calls["count"] == 1
        events_after_first = AgentEvent.query.filter_by(run_id=run_id).count()

        second = engine.run_until_interrupt(run_id, "t-second")
        assert second == "completed"
        assert calls["count"] == 1, "重复 dispatch 不得重复执行工具"
        assert AgentEvent.query.filter_by(run_id=run_id).count() == events_after_first


def test_terminal_run_dispatch_is_noop(app):
    run_id = _make_run(app)
    provider = _OneToolProvider()
    registry, calls = _registry()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=registry,
            events=EventService(),
        )
        assert engine.run_until_interrupt(run_id, "t-1") == "completed"
        run = db.session.get(AgentRun, run_id)
        run.status = AgentRunStatus.FAILED.value
        db.session.commit()
        assert engine.run_until_interrupt(run_id, "t-2") == "failed"
        assert calls["count"] == 1
