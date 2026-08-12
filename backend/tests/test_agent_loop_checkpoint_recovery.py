# -*- coding: utf-8 -*-
"""T09 Checkpoint 恢复测试：完整字段、崩溃边界、非幂等未知状态。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import (
    AgentRun,
    AgentToolCall,
)
from app.services.security_agent.checkpoint_service import CheckpointService


def _make_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="检查点测试",
        mode="hybrid",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_checkpoint_records_full_recovery_state(app):
    with app.app_context():
        run = _make_run()
        run.iteration_count = 3
        run.last_event_sequence = 42
        run.current_item_public_id = "item-9"
        checkpoint = CheckpointService().save(
            run,
            completed_node_keys=["inventory", "baseline_scan"],
            artifact_refs=[{"artifact_type": "finding_set"}],
            iteration=3,
            context_watermark=42,
            current_item_public_id="item-9",
            lease_owner="worker-1",
            pending_control_watermark=7,
            budget_snapshot={"tool_calls": 5, "llm_calls": 2},
            checkpoint_digest="sha256:abc",
        )
        restored = CheckpointService().restore(run.id)
        assert restored["plan_version"] == run.plan_version
        assert restored["completed_node_keys"] == ["inventory", "baseline_scan"]
        assert restored["iteration"] == 3
        assert restored["context_watermark"] == 42
        assert restored["current_item_public_id"] == "item-9"
        assert restored["lease_owner"] == "worker-1"
        assert restored["pending_control_watermark"] == 7
        assert restored["budget_snapshot"] == {"tool_calls": 5, "llm_calls": 2}
        assert restored["checkpoint_digest"] == "sha256:abc"
        assert checkpoint.event_sequence == 42


def test_checkpoint_restore_without_checkpoint_returns_empty(app):
    with app.app_context():
        run = _make_run()
        restored = CheckpointService().restore(run.id)
        assert restored["completed_node_keys"] == []
        assert restored["iteration"] == 0


def test_unknown_non_idempotent_tool_state_not_auto_retried(app):
    """非幂等工具处于未知（running）状态时，恢复不得自动重试。"""
    with app.app_context():
        run = _make_run()
        call = AgentToolCall(
            run_id=run.id,
            tool_name="non_idempotent_tool",
            idempotency_key=f"{run.id}:node:1",
            logical_call_key=f"{run.id}:node",
            status="running",
            risk_level="safe_read",
            started_at=None,
        )
        db.session.add(call)
        db.session.commit()
        reloaded = db.session.get(AgentToolCall, call.id)
        assert reloaded.status == "running"
        assert reloaded.retryable is False, "未知状态不得自动重试"


def test_completed_idempotent_tool_reusable_after_restore(app):
    """已完成幂等工具在恢复后复用原结果，不重复执行。"""
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentToolCall(
                run_id=run.id,
                tool_name="idem_tool",
                idempotency_key=f"{run.id}:node:1",
                logical_call_key=f"{run.id}:node",
                arguments_digest="digest-x",
                status="succeeded",
                output_summary="原结果",
                risk_level="safe_read",
            )
        )
        db.session.commit()
        from app.services.security_agent.tools.executor import ToolExecutor
        from app.services.security_agent.event_service import EventService
        from app.services.security_agent.tools.registry import ToolRegistry

        registry = ToolRegistry()

        def handler(ctx):
            raise AssertionError("已完成的幂等工具不得重复执行")

        from app.services.security_agent.tools.contracts import ToolDescriptor

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
        from app.models.agent_runtime import AgentPlanNode, AgentStepExecution

        node = AgentPlanNode(
            plan_id=1,
            node_key="node",
            node_type="repository_mapping",
            status="ready",
            title="node",
            tool_name="idem_tool",
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
        result = ToolExecutor(registry, EventService()).execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id="t-restore",
            input_payload={"x": 1},
        )
        assert result.status == "succeeded"
        assert result.metrics.get("replayed") is True
