# -*- coding: utf-8 -*-
"""T05 工具输入校验测试：非法输入必须在 Handler 前拒绝且 Handler 调用次数为零。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentStepExecution,
)
from app.services.security_agent.contracts import EVENT_TOOL_FAILED
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.contracts import (
    ToolDescriptor,
    ToolResult,
)
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import ToolRegistry


def _echo_registry() -> tuple[ToolRegistry, dict]:
    registry = ToolRegistry()
    calls = {"count": 0}

    def handler(ctx):
        calls["count"] += 1
        return ToolResult(status="succeeded", summary="echo ok")

    registry.register(
        ToolDescriptor(
            name="echo_tool",
            version="1.0",
            category="test",
            description="echo",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 10},
                    "count": {"type": "integer", "minimum": 1, "maximum": 100},
                    "file_path": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            risk_level="safe_read",
            timeout_seconds=5,
            idempotent=True,
        ),
        handler,
    )
    return registry, calls


def _run_and_node(registry: ToolRegistry, *, tool_name: str = "echo_tool") -> tuple:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="校验测试",
        mode="baseline",
    )
    db.session.add(run)
    db.session.flush()
    plan = AgentPlan(
        run_id=run.id,
        plan_version=1,
        planner_source="rule_based_policy",
        objective="校验测试",
    )
    db.session.add(plan)
    db.session.flush()
    node = AgentPlanNode(
        plan_id=plan.id,
        node_key="echo_node",
        node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
        status=AgentPlanNodeStatus.READY.value,
        title="echo",
        tool_name=tool_name,
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


def _execute(app, registry, calls, *, input_payload, tool_name="echo_tool"):
    with app.app_context():
        run, node, step = _run_and_node(registry, tool_name=tool_name)
        result = ToolExecutor(registry, EventService()).execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id="t-validate",
            input_payload=input_payload,
        )
        return result, calls["count"]


def test_unknown_tool_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(
        app,
        registry,
        calls,
        input_payload={"name": "x"},
        tool_name="not_registered",
    )
    assert count == 0
    assert result.status == "failed"
    assert result.error_code == "AGENT_TOOL_FAILED"


def test_unknown_field_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(app, registry, calls, input_payload={"name": "x", "extra": 1})
    assert count == 0
    assert result.status == "failed"
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"


def test_missing_required_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(app, registry, calls, input_payload={"count": 5})
    assert count == 0
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"


def test_wrong_type_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(app, registry, calls, input_payload={"name": 123})
    assert count == 0
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"


def test_out_of_range_integer_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(app, registry, calls, input_payload={"name": "x", "count": 999})
    assert count == 0
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"


def test_oversized_string_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(app, registry, calls, input_payload={"name": "x" * 11})
    assert count == 0
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"


def test_malicious_path_rejected_before_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(
        app,
        registry,
        calls,
        input_payload={"name": "x", "file_path": "../etc/passwd"},
    )
    assert count == 0
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"

    result, count = _execute(
        app,
        registry,
        calls,
        input_payload={"name": "x", "file_path": "C:\\Windows\\system32"},
    )
    assert count == 0
    assert result.error_code == "AGENT_TOOL_INPUT_INVALID"


def test_valid_input_reaches_handler(app):
    registry, calls = _echo_registry()
    result, count = _execute(app, registry, calls, input_payload={"name": "ok", "count": 3})
    assert count == 1
    assert result.status == "succeeded"


def test_input_invalid_emits_failed_event(app):
    with app.app_context():
        registry, calls = _echo_registry()
        run, node, step = _run_and_node(registry)
        ToolExecutor(registry, EventService()).execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id="t-event",
            input_payload={"extra": 1},
        )
        failed = AgentEvent.query.filter_by(
            run_id=run.id, event_type=EVENT_TOOL_FAILED
        ).first()
        assert failed is not None
        assert failed.payload_json["error_code"] == "AGENT_TOOL_INPUT_INVALID"
