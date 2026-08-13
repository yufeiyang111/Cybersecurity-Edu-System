# -*- coding: utf-8 -*-
"""审批闭环（requires_approval/request_approval）与 Retry API 测试。"""
from __future__ import annotations

from app import db
from app.models.agent_approval import AgentApproval, ApprovalOperationType
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
from app.services.security_agent.state_machine import AgentStateMachine
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolResult,
)
from app.services.security_agent.tools.registry import ToolRegistry

from test_agent_run_api import auth_headers, make_project_and_snapshot, make_user


def _make_run(*, status=AgentRunStatus.EXECUTING_TOOLS.value) -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="审批闭环测试",
        mode="hybrid",
        status=status,
    )
    db.session.add(run)
    db.session.flush()
    plan = AgentPlan(
        run_id=run.id,
        plan_version=1,
        planner_source="rule_based_policy",
        objective=run.goal_text,
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
    return run


class _ApprovalToolProvider:
    """第一轮请求敏感工具 → 第二轮在审批恢复后最终回答。"""

    provider_name = "approval-provider"
    model = "approval-model"
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
                        call_id="call-sensitive",
                        name="sensitive_tool",
                        arguments={"query": "x"},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name=self.provider_name,
                model=self.model,
            )
        return AgentModelResponse(
            content="审查完成：审批通过后已确认执行范围。",
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
        )


def _registry_with_sensitive_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="sensitive_tool",
            version="1.0",
            category="test",
            description="需要审批的敏感工具",
            input_schema={"type": "object", "properties": {}},
            risk_level="sensitive_read",
            timeout_seconds=5,
            idempotent=True,
            requires_approval=True,
        ),
        lambda ctx: ToolResult(status="succeeded", summary="敏感工具已执行"),
    )
    return registry


def test_tool_requires_approval_interrupts_with_persisted_approval(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        run = _make_run()
        engine = AgentLoopEngine(
            provider=_ApprovalToolProvider(),
            registry=_registry_with_sensitive_tool(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run.id, "t-approval-tool")
        run = db.session.get(AgentRun, run.id)
        assert result == "interrupted"
        assert run.status == AgentRunStatus.AWAITING_APPROVAL.value

        approvals = AgentApproval.query.filter_by(run_id=run.id).all()
        assert len(approvals) == 1, "requires_approval 拦截必须持久化审批行"
        approval = approvals[0]
        assert approval.operation_type == ApprovalOperationType.TOOL_EXECUTION.value
        assert approval.status == "pending"
        assert approval.affected_scope_json["tool_name"] == "sensitive_tool"
        assert "arguments_digest" in approval.affected_scope_json

        events = [
            event.event_type
            for event in AgentEvent.query.filter_by(run_id=run.id).all()
        ]
        assert "item.approval.requested" in events


def test_model_request_approval_action_persists_and_rejects_unknown_tool(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True

        class _RequestApprovalProvider(_ApprovalToolProvider):
            def generate_agent(self, request):
                self.requests.append(request)
                from app.services.security_agent.model.contracts import (
                    AgentModelResponse,
                )

                return AgentModelResponse(
                    content=None,
                    tool_calls=(),
                    finish_reason="stop",
                    provider_name=self.provider_name,
                    model=self.model,
                    action_kind="request_approval",
                    action_payload={
                        "request_id": "req-1",
                        "tool_name": "sensitive_tool",
                        "reason": "模型请求执行敏感工具",
                    },
                )

        run = _make_run()
        engine = AgentLoopEngine(
            provider=_RequestApprovalProvider(),
            registry=_registry_with_sensitive_tool(),
            events=EventService(),
        )
        result = engine.run_until_interrupt(run.id, "t-approval-action")
        run = db.session.get(AgentRun, run.id)
        assert result == "interrupted"
        assert run.status == AgentRunStatus.AWAITING_APPROVAL.value
        approval = AgentApproval.query.filter_by(run_id=run.id).one()
        assert approval.operation_type == ApprovalOperationType.TOOL_EXECUTION.value
        assert approval.affected_scope_json["request_id"] == "req-1"


def test_model_request_approval_rejected_for_unknown_tool(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True

        class _BadApprovalProvider(_ApprovalToolProvider):
            def generate_agent(self, request):
                self.requests.append(request)
                from app.services.security_agent.model.contracts import (
                    AgentModelResponse,
                )

                return AgentModelResponse(
                    content=None,
                    tool_calls=(),
                    finish_reason="stop",
                    provider_name=self.provider_name,
                    model=self.model,
                    action_kind="request_approval",
                    action_payload={
                        "request_id": "req-x",
                        "tool_name": "not_registered_tool",
                        "reason": "尝试绕过注册表",
                    },
                )

        run = _make_run()
        result = AgentLoopEngine(
            provider=_BadApprovalProvider(),
            registry=_registry_with_sensitive_tool(),
            events=EventService(),
        ).run_until_interrupt(run.id, "t-approval-bad")
        assert AgentApproval.query.filter_by(run_id=run.id).count() == 0, (
            "未注册工具不得产生审批行"
        )


def test_retry_rejects_completed_and_requires_terminal_recoverable(app):
    completed = _make_run(status=AgentRunStatus.COMPLETED.value)
    with app.app_context():
        from app.services.security_agent.state_machine import AgentStateError

        try:
            AgentStateMachine().retry(completed, actor_id=1, reason="test")
            assert False, "completed 不能重试"
        except AgentStateError:
            pass
        partial = _make_run(status=AgentRunStatus.PARTIAL.value)
        AgentStateMachine().retry(partial, actor_id=1, reason="用户重试")
        db.session.refresh(partial)
        assert partial.status == AgentRunStatus.QUEUED.value
        assert partial.finished_at is None


def test_retry_endpoint_flow(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "retryowner", "retryowner@t")
    project_id, _ = make_project_and_snapshot(
        agent_api_app, tmp_path, user_id, workspace_id
    )
    with agent_api_app.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=1,
            created_by=user_id,
            goal_text="retry 端点",
            mode="baseline",
            status=AgentRunStatus.PARTIAL.value,
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)
    response = client.post(
        f"/api/security/agent-runs/{run_id}/retry",
        headers=headers,
        data=b"",
        content_type="application/json",
    )
    assert response.status_code == 200, "空 body 的 retry 不得 500（client_request_id 自动生成）"
    body = response.get_json()
    assert body["retried"] is True
    assert body["control_input"]["input_type"] == "system_retry"
    # agent_api_app 使用同步 executor：retry 后 run 会被立即重新执行，
    # 状态在 queued 与各终态之间；核心断言是重新入队 + 控制输入落库。
    assert body["run"]["status"] in {
        "queued",
        "completed",
        "completed_with_warnings",
        "partial",
        "failed",
    }

    response = client.post(
        f"/api/security/agent-runs/{run_id}/retry",
        headers=headers,
        json={"client_request_id": "retry-fixed-1"},
    )
    assert response.status_code == 409, "queued 状态不可再次 retry"

    outsider_id, _ = make_user(agent_api_app, "retry-outsider", "retry-out@t")
    with agent_api_app.app_context():
        run2 = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=1,
            created_by=user_id,
            goal_text="retry 越权",
            mode="baseline",
            status=AgentRunStatus.FAILED.value,
        )
        db.session.add(run2)
        db.session.commit()
        run2_id = run2.id
    response = client.post(
        f"/api/security/agent-runs/{run2_id}/retry",
        headers=auth_headers(agent_api_app, outsider_id),
        json={},
    )
    assert response.status_code == 403, "非成员不能重试他人任务"
