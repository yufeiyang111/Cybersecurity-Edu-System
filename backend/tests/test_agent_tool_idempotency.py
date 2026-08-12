# -*- coding: utf-8 -*-
"""T05 幂等测试：logical_call_key + arguments_digest 复用已完成结果。"""
from __future__ import annotations

import hashlib
import json

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentStepExecution,
    AgentToolCall,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolResult,
)
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import ToolRegistry


def _setup(app):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="幂等测试",
            mode="baseline",
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="幂等测试",
        )
        db.session.add(plan)
        db.session.flush()
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key="idem_node",
            node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
            status=AgentPlanNodeStatus.READY.value,
            title="node",
            tool_name="idem_tool",
        )
        db.session.add(node)
        db.session.flush()

        calls = {"count": 0}
        registry = ToolRegistry()

        def handler(ctx):
            calls["count"] += 1
            return ToolResult(status="succeeded", summary="确定性结果")

        registry.register(
            ToolDescriptor(
                name="idem_tool",
                version="1.0",
                category="test",
                description="idem",
                input_schema={"type": "object", "properties": {}},
                risk_level="safe_read",
                timeout_seconds=5,
                idempotent=True,
            ),
            handler,
        )
        return run, node, registry, calls


def _execute(app, run, node, registry, *, input_payload=None, attempt=1):
    step = AgentStepExecution(
        plan_node_id=node.id,
        run_id=run.id,
        attempt_number=attempt,
        status="running",
    )
    db.session.add(step)
    db.session.flush()
    return ToolExecutor(registry, EventService()).execute(
        run,
        node,
        step,
        actor_id=run.created_by,
        trace_id="t-idem",
        input_payload=input_payload,
    )


def test_same_logical_call_and_arguments_reuses_result(app):
    run, node, registry, calls = _setup(app)
    first = _execute(app, run, node, registry, input_payload={"query": "auth"})
    assert first.status == "succeeded"
    assert calls["count"] == 1

    second = _execute(app, run, node, registry, input_payload={"query": "auth"}, attempt=2)
    assert second.status == "succeeded"
    assert calls["count"] == 1, "相同 logical_call_key + arguments_digest 必须复用结果"
    assert second.metrics.get("replayed") is True


def test_different_arguments_executes_again(app):
    run, node, registry, calls = _setup(app)
    _execute(app, run, node, registry, input_payload={"query": "auth"})
    _execute(app, run, node, registry, input_payload={"query": "sql"}, attempt=2)
    assert calls["count"] == 2


def test_replay_requires_succeeded_status(app):
    run, node, registry, calls = _setup(app)
    first = _execute(app, run, node, registry, input_payload={"query": "x"})
    assert first.status == "succeeded"
    call = AgentToolCall.query.filter_by(
        run_id=run.id, plan_node_id=node.id
    ).one()
    call.status = "failed"
    db.session.commit()

    second = _execute(app, run, node, registry, input_payload={"query": "x"}, attempt=2)
    assert calls["count"] == 2, "failed 状态不得复用，必须重新执行"
    assert second.metrics.get("replayed") is not True
