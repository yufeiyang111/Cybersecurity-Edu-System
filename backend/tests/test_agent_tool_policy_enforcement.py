# -*- coding: utf-8 -*-
"""T05 工具策略强制测试：prohibited/审批/模式/预算/暂停取消。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_approval import (
    AgentApproval,
    ApprovalOperationType,
    ApprovalRiskLevel,
    ApprovalStatus,
)
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
    AgentStepExecution,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolResult,
)
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import ToolRegistry


def _register_tool(
    registry: ToolRegistry,
    *,
    name: str,
    risk_level: str = "safe_read",
    requires_approval: bool = False,
    allowed_modes: tuple[str, ...] = ("baseline", "hybrid", "deep_audit"),
) -> dict:
    calls = {"count": 0}

    def default_handler(ctx):
        calls["count"] += 1
        return ToolResult(status="succeeded", summary=f"{name} ok")

    registry.register(
        ToolDescriptor(
            name=name,
            version="1.0",
            category="test",
            description=name,
            input_schema={"type": "object", "properties": {}},
            risk_level=risk_level,
            timeout_seconds=5,
            idempotent=True,
            requires_approval=requires_approval,
            allowed_modes=allowed_modes,
        ),
        default_handler,
    )
    return calls


def _setup(app, *, mode="baseline", status=AgentRunStatus.EXECUTING_TOOLS):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="策略测试",
            mode=mode,
            status=status,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="策略测试",
        )
        db.session.add(plan)
        db.session.flush()
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key="node_1",
            node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
            status=AgentPlanNodeStatus.READY.value,
            title="node",
            tool_name="tool_x",
        )
        db.session.add(node)
        db.session.flush()
        step = AgentStepExecution(
            plan_node_id=node.id,
            run_id=run.id,
            attempt_number=1,
            status="running",
        )
        db.session.add(step)
        db.session.flush()
        return run, node, step


def test_prohibited_tool_never_executes(app):
    registry = ToolRegistry()
    calls = _register_tool(registry, name="evil_tool", risk_level="prohibited")
    run, node, step = _setup(app)
    node.tool_name = "evil_tool"
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-prohibited"
    )
    assert calls["count"] == 0
    assert result.status == "failed"
    assert result.error_code == "AGENT_TOOL_NOT_ALLOWED"


def test_sensitive_tool_requires_approved_approval(app):
    registry = ToolRegistry()
    calls = _register_tool(
        registry,
        name="sensitive_tool",
        risk_level="sensitive_read",
        requires_approval=True,
    )
    run, node, step = _setup(app)
    node.tool_name = "sensitive_tool"
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-approval"
    )
    assert calls["count"] == 0
    assert result.error_code == "AGENT_APPROVAL_REQUIRED"

    db.session.add(
        AgentApproval(
            run_id=run.id,
            workspace_id=run.workspace_id,
            operation_type=ApprovalOperationType.REMOTE_SOURCE_SEND.value,
            risk_level=ApprovalRiskLevel.HIGH.value,
            reason="工具审批测试",
            status=ApprovalStatus.APPROVED.value,
            requested_by=run.created_by,
            operation_digest=f"approve-{node.id}",
        )
    )
    db.session.commit()
    approved_result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-approval-2"
    )
    assert calls["count"] == 1
    assert approved_result.status == "succeeded"


def test_mode_not_allowed_rejected(app):
    registry = ToolRegistry()
    calls = _register_tool(
        registry,
        name="baseline_only_tool",
        allowed_modes=("baseline",),
    )
    run, node, step = _setup(app, mode="deep_audit")
    node.tool_name = "baseline_only_tool"
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-mode"
    )
    assert calls["count"] == 0
    assert result.error_code == "AGENT_TOOL_NOT_ALLOWED"


def test_budget_exhausted_rejects_new_tool(app):
    registry = ToolRegistry()
    calls = _register_tool(registry, name="budget_tool")
    run, node, step = _setup(app)
    run.max_tool_calls = 2
    run.tool_call_count = 2
    node.tool_name = "budget_tool"
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-budget"
    )
    assert calls["count"] == 0
    assert result.error_code == "AGENT_BUDGET_EXHAUSTED"


def test_paused_or_canceled_run_rejects_tool(app):
    registry = ToolRegistry()
    calls = _register_tool(registry, name="state_tool")
    for status in (AgentRunStatus.PAUSED, AgentRunStatus.CANCELED):
        run, node, step = _setup(app, status=status)
        node.tool_name = "state_tool"
        result = ToolExecutor(registry, EventService()).execute(
            run, node, step, actor_id=run.created_by, trace_id="t-state"
        )
        assert calls["count"] == 0
        assert result.status == "failed"


def test_unknown_risk_level_registration_rejected():
    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.register(
            ToolDescriptor(
                name="bad_risk",
                version="1.0",
                category="test",
                description="bad",
                input_schema={"type": "object", "properties": {}},
                risk_level="totally_unsafe_level",
                timeout_seconds=5,
                idempotent=True,
            ),
            lambda ctx: ToolResult(),
        )
