# -*- coding: utf-8 -*-
"""T05 超时与重试测试：硬超时迟到结果不写成功；自动重试条件严格。"""
from __future__ import annotations

import time

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


def _setup(
    app,
    *,
    timeout_seconds=5,
    retry_policy=None,
    idempotent=True,
    handler=None,
):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="超时重试测试",
            mode="baseline",
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="超时重试测试",
        )
        db.session.add(plan)
        db.session.flush()
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key="node_retry",
            node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
            status=AgentPlanNodeStatus.READY.value,
            title="node",
            tool_name="retry_tool",
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

        registry = ToolRegistry()
        registry.register(
            ToolDescriptor(
                name="retry_tool",
                version="1.0",
                category="test",
                description="retry",
                input_schema={"type": "object", "properties": {}},
                risk_level="safe_read",
                timeout_seconds=timeout_seconds,
                idempotent=idempotent,
                retry_policy=retry_policy,
            ),
            handler,
        )
        return run, node, step, registry


def test_late_result_after_hard_timeout_not_succeeded(app):
    def slow_handler(ctx):
        time.sleep(1.5)
        return ToolResult(status="succeeded", summary="迟到的成功")

    run, node, step, registry = _setup(
        app, timeout_seconds=1, handler=slow_handler
    )
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-late"
    )
    assert result.status == "failed"
    assert result.error_code == "AGENT_TOOL_TIMEOUT"
    call = AgentToolCall.query.filter_by(
        run_id=run.id, plan_node_id=node.id
    ).one()
    assert call.status != "succeeded"
    assert call.error_code == "AGENT_TOOL_TIMEOUT"


def test_automatic_retry_within_policy(app):
    attempts = {"count": 0}

    def flaky_handler(ctx):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return ToolResult(
                status="failed",
                summary="第一次失败",
                error_code="AGENT_TOOL_FAILED",
                warning_codes=["AGENT_TOOL_FAILED"],
                retryable=True,
            )
        return ToolResult(status="succeeded", summary="第二次成功")

    run, node, step, registry = _setup(
        app,
        retry_policy={
            "max_attempts": 2,
            "retryable_warning_codes": ["AGENT_TOOL_FAILED"],
        },
        handler=flaky_handler,
    )
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-retry"
    )
    assert attempts["count"] == 2
    assert result.status == "succeeded"
    calls = AgentToolCall.query.filter_by(run_id=run.id, plan_node_id=node.id).all()
    assert len(calls) == 2
    assert {call.attempt_number for call in calls} == {1, 2}
    assert {call.logical_call_key for call in calls} == {f"{run.id}:node_retry"}


def test_non_idempotent_tool_never_auto_retried(app):
    attempts = {"count": 0}

    def flaky_handler(ctx):
        attempts["count"] += 1
        return ToolResult(
            status="failed",
            summary="失败",
            error_code="AGENT_TOOL_FAILED",
            retryable=True,
        )

    run, node, step, registry = _setup(
        app,
        idempotent=False,
        retry_policy={
            "max_attempts": 3,
            "retryable_warning_codes": ["AGENT_TOOL_FAILED"],
        },
        handler=flaky_handler,
    )
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-nonidem"
    )
    assert attempts["count"] == 1
    assert result.status == "failed"


def test_warning_code_not_in_allowlist_never_retried(app):
    attempts = {"count": 0}

    def flaky_handler(ctx):
        attempts["count"] += 1
        return ToolResult(
            status="failed",
            summary="失败",
            error_code="AGENT_TOOL_FAILED",
            warning_codes=["AGENT_TOOL_INPUT_INVALID"],
            retryable=True,
        )

    run, node, step, registry = _setup(
        app,
        retry_policy={
            "max_attempts": 3,
            "retryable_warning_codes": ["AGENT_TOOL_TIMEOUT"],
        },
        handler=flaky_handler,
    )
    result = ToolExecutor(registry, EventService()).execute(
        run, node, step, actor_id=run.created_by, trace_id="t-allowlist"
    )
    assert attempts["count"] == 1
    assert result.status == "failed"
