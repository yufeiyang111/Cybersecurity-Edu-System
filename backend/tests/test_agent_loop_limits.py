# -*- coding: utf-8 -*-
"""T08 Loop 限制测试：超轮数、预算耗尽、连续模型错误、重复动作。"""
from __future__ import annotations

from app import db
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
from app.services.security_agent.tools.registry import ToolRegistry


class _ErrorProvider:
    provider_name = "error"
    model = "error-model"
    model_version = "1"
    provider_config_id = None

    def __init__(self, error: str) -> None:
        self.error = error
        self.requests = []

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True)

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        return AgentModelResponse(
            content=None,
            tool_calls=(),
            finish_reason=None,
            provider_name=self.provider_name,
            model=self.model,
            warning_code=self.error,
        )


class _ToolLoopProvider:
    """每次都请求同一个工具（重复动作死循环场景）。"""

    provider_name = "tool-loop"
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
            content=None,
            tool_calls=(
                AgentModelToolCall(
                    call_id=f"call-{len(self.requests)}",
                    name="echo_tool",
                    arguments={"query": "same"},
                ),
            ),
            finish_reason="tool_calls",
            provider_name=self.provider_name,
            model=self.model,
        )


def _make_run(app, *, mode="hybrid", max_iterations=None, max_tool_calls=None):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="限制测试",
            mode=mode,
            status=AgentRunStatus.EXECUTING_TOOLS.value,
            max_iterations=max_iterations or 20,
            max_tool_calls=max_tool_calls or 30,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="限制测试",
        )
        db.session.add(plan)
        db.session.flush()
        for key, node_type in (
            ("inventory", AgentPlanNodeType.INVENTORY.value),
            ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value),
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


def _echo_registry() -> ToolRegistry:
    from app.services.security_agent.tools.contracts import (
        ToolDescriptor,
        ToolResult,
    )

    registry = ToolRegistry()

    def handler(ctx):
        return ToolResult(status="succeeded", summary="echo")

    registry.register(
        ToolDescriptor(
            name="echo_tool",
            version="1.0",
            category="test",
            description="echo",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=5,
            idempotent=True,
        ),
        handler,
    )
    return registry


def test_iteration_limit_reached_stops_loop(app):
    run_id = _make_run(app, max_iterations=3)
    provider = _ToolLoopProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_echo_registry(),
            events=EventService(),
            max_iterations=3,
            max_same_tool_same_args=100,
        )
        result = engine.run_until_interrupt(run_id, "t-iter")
        run = db.session.get(AgentRun, run_id)
        assert result in {"partial", "completed_with_warnings"}
        assert run.iteration_count >= 3
        assert "AGENT_ITERATION_LIMIT_REACHED" in (run.warning_codes or [])


def test_budget_exhausted_stops_new_tools(app):
    run_id = _make_run(app, max_tool_calls=1)
    provider = _ToolLoopProvider()
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        run.tool_call_count = 1
        db.session.commit()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_echo_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-budget")
        run = db.session.get(AgentRun, run_id)
        assert result in {"partial", "completed_with_warnings"}
        assert "AGENT_BUDGET_EXHAUSTED" in (run.warning_codes or [])


def test_consecutive_model_errors_degrade_loop(app):
    run_id = _make_run(app)
    provider = _ErrorProvider("LLM_PROVIDER_TIMEOUT")
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_echo_registry(),
            events=EventService(),
            max_consecutive_model_errors=2,
        )
        result = engine.run_until_interrupt(run_id, "t-errors")
        assert result in {"partial", "failed"}
        assert len(provider.requests) <= 3


def test_same_tool_same_arguments_repeated_stops_loop(app):
    run_id = _make_run(app)
    provider = _ToolLoopProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_echo_registry(),
            events=EventService(),
            max_same_tool_same_args=2,
        )
        result = engine.run_until_interrupt(run_id, "t-repeat")
        run = db.session.get(AgentRun, run_id)
        assert result in {"partial", "completed_with_warnings"}
        assert "AGENT_REPEATED_TOOL_CALL" in (run.warning_codes or [])
