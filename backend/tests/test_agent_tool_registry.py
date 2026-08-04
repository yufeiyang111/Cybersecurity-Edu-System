"""Tool registry and executor idempotency tests."""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentStepExecution,
    AgentToolCall,
)
from app.models.security import Workspace, WorkspaceMember, WorkspaceMemberRole
from app.models.user import User
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.contracts import ToolDescriptor, ToolResult
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import ToolRegistry, get_tool_registry


def test_registry_resolves_and_rejects(app):
    registry = ToolRegistry()
    handler = lambda ctx: ToolResult(summary="ok")
    registry.register(
        ToolDescriptor(name="ping", version="1", category="test", description="ping"), handler
    )
    descriptor, resolved = registry.resolve("ping")
    assert descriptor.name == "ping"
    assert resolved is handler
    with pytest.raises(KeyError):
        registry.resolve("missing")
    with pytest.raises(ValueError):
        registry.register(
            ToolDescriptor(name="ping", version="1", category="test", description="ping"), handler
        )


def test_default_registry_has_a1_tools(app):
    registry = get_tool_registry()
    assert registry.has("inventory_snapshot")
    assert registry.has("finalize_agent_report")
    descriptors = {item.name: item for item in registry.descriptors()}
    assert descriptors["inventory_snapshot"].risk_level == "safe_read"
    assert descriptors["inventory_snapshot"].idempotent is True


@pytest.fixture
def run_with_node(app):
    with app.app_context():
        user = User(username="carol", email="carol@example.test", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name="w", slug="w-3")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceMemberRole.OWNER.value)
        )
        run = AgentRun(
            workspace_id=workspace.id,
            project_id=1,
            snapshot_id=1,
            created_by=user.id,
            goal_text="g",
            mode=AgentRunMode.BASELINE.value,
            status=AgentRunStatus.EXECUTING_TOOLS.value,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
        db.session.add(plan)
        db.session.flush()
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key="inventory",
            node_type=AgentPlanNodeType.INVENTORY.value,
            status=AgentPlanNodeStatus.READY.value,
            title="清点",
            tool_name="finalize_agent_report",
        )
        db.session.add(node)
        db.session.flush()
        step = AgentStepExecution(plan_node_id=node.id, run_id=run.id, attempt_number=1, status="running")
        db.session.add(step)
        db.session.commit()
        yield run, node, step


def test_executor_idempotency_key_prevents_duplicate_execution(run_with_node, app):
    with app.app_context():
        run, node, step = run_with_node
        executor = ToolExecutor(get_tool_registry(), EventService())
        first = executor.execute(run, node, step, actor_id=run.created_by, trace_id="t")
        assert first.status == "succeeded"
        calls = AgentToolCall.query.filter_by(plan_node_id=node.id).all()
        assert len(calls) == 1

        replay = executor.execute(run, node, step, actor_id=run.created_by, trace_id="t")
        assert replay.status == "succeeded"
        assert replay.metrics.get("replayed") is True, "幂等重放必须返回已存结果而不是重新执行"
        assert len(AgentToolCall.query.filter_by(plan_node_id=node.id).all()) == 1
        assert run.tool_call_count == 1


def test_unknown_tool_raises(run_with_node, app):
    with app.app_context():
        run, node, step = run_with_node
        node.tool_name = "not_registered_tool"
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        with pytest.raises(KeyError):
            executor.execute(run, node, step, actor_id=run.created_by, trace_id="t")
