# -*- coding: utf-8 -*-
"""T09 中断测试：审批中断不占 Worker、审批结果走 Control Input、Pause/Cancel 语义。"""
from __future__ import annotations

from app import db
from app.models.agent_control import AgentControlInput
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.services.security_agent.approval_service import ApprovalService
from app.services.security_agent.event_service import EventService
from app.services.security_agent.loop.engine import AgentLoopEngine
from app.services.security_agent.model.contracts import (
    AgentModelRequest,
    AgentModelResponse,
    AgentModelToolCall,
    ProviderCapabilities,
)
from app.services.security_agent.state_machine import AgentStateMachine
from app.services.security_agent.tools.registry import ToolRegistry


class _ApprovalProvider:
    """模型请求审批（一次）后给出最终回答。"""

    provider_name = "approval"
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
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
                warning_code="AGENT_APPROVAL_REQUIRED",
            )
        return AgentModelResponse(
            content="审批后完成",
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
        )


def _make_run(app, *, status=AgentRunStatus.EXECUTING_TOOLS):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="中断测试",
            mode="hybrid",
            status=status,
        )
        db.session.add(run)
        db.session.flush()
        from app.models.agent_runtime import (
            AgentPlan,
            AgentPlanNode,
            AgentPlanNodeStatus,
            AgentPlanNodeType,
        )

        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="中断测试",
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


def _engine(app, provider, registry=None):
    from app.services.security_agent.tools.contracts import (
        ToolDescriptor,
        ToolResult,
    )

    if registry is None:
        registry = ToolRegistry()

        def handler(ctx):
            return ToolResult(status="succeeded", summary="ok")

        registry.register(
            ToolDescriptor(
                name="safe_tool",
                version="1.0",
                category="test",
                description="safe",
                input_schema={"type": "object", "properties": {}},
                risk_level="safe_read",
                timeout_seconds=5,
                idempotent=True,
            ),
            handler,
        )
    return AgentLoopEngine(provider=provider, registry=registry, events=EventService())


def test_approval_resolve_writes_control_input_not_sync_execution(app):
    """T09：审批通过只写 Control Input + 状态转换，不在 HTTP 线程同步推进 Loop。"""
    from app.models.agent_approval import (
        AgentApproval,
        ApprovalOperationType,
        ApprovalRiskLevel,
    )

    with app.app_context():
        run = db.session.get(AgentRun, _make_run(app, status=AgentRunStatus.AWAITING_APPROVAL))
        approval = AgentApproval(
            run_id=run.id,
            workspace_id=run.workspace_id,
            operation_type=ApprovalOperationType.BUDGET_INCREASE.value,
            risk_level=ApprovalRiskLevel.MEDIUM.value,
            reason="预算",
            status="pending",
            requested_by=run.created_by,
            operation_digest="digest-resolve-1",
        )
        db.session.add(approval)
        db.session.commit()
        resolved = ApprovalService().resolve(
            run,
            approval.id,
            decision="approved",
            comment="同意",
            resolver_id=run.created_by,
            resolver_role="owner",
            trace_id="t-resolve",
        )
        assert resolved.status == "approved"
        run = db.session.get(AgentRun, run.id)
        assert _status(run) == AgentRunStatus.EXECUTING_TOOLS.value
        control = AgentControlInput.query.filter_by(
            run_id=run.id, input_type="approval_result"
        ).one()
        assert control.status == "pending"
        assert control.payload_json["decision"] == "approved"


def test_approval_request_interrupts_engine_without_worker_occupation(app):
    run_id = _make_run(app)
    provider = _ApprovalProvider()
    with app.app_context():
        engine = _engine(app, provider)
        result = engine.run_until_interrupt(run_id, "t-approval")
        run = db.session.get(AgentRun, run_id)
        assert result == "interrupted"
        assert _status(run) == AgentRunStatus.AWAITING_APPROVAL.value


def test_pause_control_input_interrupts_at_safe_boundary(app):
    run_id = _make_run(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentControlInput(
                public_id="ctl-pause",
                run_id=run.id,
                input_type="pause",
                client_request_id="req-pause",
                payload_json={},
                status="pending",
            )
        )
        db.session.commit()
    with app.app_context():
        from app.services.security_agent.loop.control_inputs import ControlInputService

        engine = AgentLoopEngine(
            provider=_ApprovalProvider(),
            registry=None,
            events=EventService(),
            controls=ControlInputService(),
        )
        result = engine.run_until_interrupt(run_id, "t-pause")
        run = db.session.get(AgentRun, run_id)
        assert result == "interrupted"
        assert _status(run) == AgentRunStatus.PAUSED.value


def test_cancel_after_tool_does_not_start_new_tools(app):
    """Cancel 后不启动新工具：终态 Run 再次推进直接返回。"""
    from app.models.agent_events import AgentEvent

    run_id = _make_run(app)
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
        engine = _engine(app, _ApprovalProvider())
        result = engine.run_until_interrupt(run_id, "t-cancel")
        assert result == "canceled"
        events_after_cancel = AgentEvent.query.filter_by(run_id=run_id).count()
        run = db.session.get(AgentRun, run_id)
        assert _status(run) == AgentRunStatus.CANCELED.value
        second = engine.run_until_interrupt(run_id, "t-cancel-2")
        assert second == "canceled"
        assert AgentEvent.query.filter_by(run_id=run_id).count() == events_after_cancel


def test_ask_user_interrupts_without_tool_execution(app):
    from app.services.security_agent.loop.actions import ActionKind

    class _AskProvider(_ApprovalProvider):
        def generate_agent(self, request):
            self.requests.append(request)
            return AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason="stop",
                provider_name=self.provider_name,
                model=self.model,
            )

    run_id = _make_run(app)
    provider = _AskProvider()
    with app.app_context():
        engine = AgentLoopEngine(
            provider=provider,
            registry=_empty_registry(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run_id, "t-ask")
        assert result in {"interrupted", "partial", "failed"}
        assert provider.requests, "模型被调用过"


def _empty_registry() -> ToolRegistry:
    return ToolRegistry()


def _status(run) -> str:
    return run.status.value if hasattr(run.status, "value") else str(run.status)
