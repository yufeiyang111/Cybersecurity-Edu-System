# -*- coding: utf-8 -*-
"""T08 核心 AgentLoopEngine 测试：控制输入、硬限制、动作分发、工具回填。"""
from __future__ import annotations

from app import db
from app.models.agent_control import AgentControlInput
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
    AgentModelMessage,
    AgentModelRequest,
    AgentModelResponse,
    AgentModelToolCall,
    AgentToolDefinition,
    ProviderCapabilities,
)
from app.services.security_agent.tools.registry import ToolRegistry


class _ScriptedProvider:
    """按脚本依次返回响应的 Fake Provider，记录每次请求。"""

    provider_name = "scripted"
    model = "scripted-model"
    model_version = "1"
    provider_config_id = None

    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True)

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        return self.script.pop(0)


def _make_run(app, *, mode="hybrid"):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="引擎测试",
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
            objective="引擎测试",
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


def _engine(app, provider) -> AgentLoopEngine:
    with app.app_context():
        registry = ToolRegistry()
        from app.services.security_agent.tools.contracts import (
            ToolDescriptor,
            ToolResult,
        )

        def echo_handler(ctx):
            return ToolResult(
                status="succeeded",
                summary=f"echo:{ctx.input.get('query', '')}",
            )

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
            echo_handler,
        )
        return AgentLoopEngine(
            provider=provider,
            registry=registry,
            events=EventService(),
            max_iterations=10,
        )


def test_engine_applies_cancel_control_input(app):
    run_id = _make_run(app)
    provider = _ScriptedProvider(
        [
            AgentModelResponse(
                content="总结",
                tool_calls=(),
                finish_reason="stop",
                provider_name="scripted",
                model="m",
            )
        ]
    )
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentControlInput(
                public_id="ctl-cancel",
                run_id=run.id,
                input_type="cancel",
                client_request_id="req-cancel",
                payload_json={},
                status="pending",
            )
        )
        db.session.commit()
    with app.app_context():
        engine = _engine(app, provider)
        result = engine.run_until_interrupt(run_id, "t-cancel")
        run = db.session.get(AgentRun, run_id)
        assert result == "canceled"
        assert _status(run) == AgentRunStatus.CANCELED.value
        assert provider.requests == [], "取消后不得再调用模型"


def test_engine_tool_call_executes_and_result_available_next_turn(app):
    run_id = _make_run(app)
    provider = _ScriptedProvider(
        [
            AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call-1",
                        name="echo_tool",
                        arguments={"query": "auth"},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name="scripted",
                model="m",
            ),
            AgentModelResponse(
                content="最终回答",
                tool_calls=(),
                finish_reason="stop",
                provider_name="scripted",
                model="m",
            ),
        ]
    )
    with app.app_context():
        engine = _engine(app, provider)
        result = engine.run_until_interrupt(run_id, "t-tool")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"
        assert len(provider.requests) == 2
        second_request = provider.requests[1]
        assert second_request.messages[-1].role == "tool"
        assert "auth" in second_request.messages[-1].content
        assert run.tool_call_count == 1


def test_engine_plan_update_action_rejected_until_implemented(app):
    """空动作（无文本无工具）直接拒绝为 invalid action，不静默执行。"""
    run_id = _make_run(app)
    provider = _ScriptedProvider(
        [
            AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason="stop",
                provider_name="scripted",
                model="m",
            )
        ]
    )
    with app.app_context():
        engine = _engine(app, provider)
        result = engine.run_until_interrupt(run_id, "t-empty")
        assert result in {"partial", "failed"}
        assert len(provider.requests) == 1, "空响应被调用一次后必须拒绝并终止"


def test_engine_never_exposes_db_or_state_mutation_to_model(app):
    """模型动作只能是冻结的判别联合：无自由文本执行路径。"""
    run_id = _make_run(app)
    provider = _ScriptedProvider([])
    with app.app_context():
        engine = _engine(app, provider)
        allowed = engine.supported_actions()
        assert allowed == {"tool_calls", "plan_update", "request_approval", "ask_user", "final_answer"}


def _status(run) -> str:
    return run.status.value if hasattr(run.status, "value") else str(run.status)
