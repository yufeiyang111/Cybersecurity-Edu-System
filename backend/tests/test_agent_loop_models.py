# -*- coding: utf-8 -*-
"""T02 模型约束测试：public_id 唯一、control 幂等唯一、摘要版本唯一、生命周期与兼容。

SQLite 测试环境不强制外键（项目现有约定），FK 完整性由 MySQL 迁移 DDL 与
业务创建顺序保证；本文件验证唯一约束、字段可写与旧数据兼容。
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.agent_control import AgentControlInput, AgentConversationSummary
from app.models.agent_events import AgentEvent
from app.models.agent_items import AgentItem
from app.models.agent_runtime import AgentCheckpoint, AgentMessage, AgentRun, AgentToolCall


def _make_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="测试目标",
        mode="baseline",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_agent_item_public_id_unique(app):
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentItem(
                public_id="item-1",
                run_id=run.id,
                item_type="tool_call",
                status="started",
            )
        )
        db.session.flush()
        db.session.add(
            AgentItem(
                public_id="item-1",
                run_id=run.id,
                item_type="tool_call",
                status="started",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_agent_item_lifecycle_fields_and_serialization(app):
    with app.app_context():
        run = _make_run()
        item = AgentItem(
            public_id="item-2",
            conversation_id=5,
            turn_id=8,
            run_id=run.id,
            iteration=3,
            item_type="reasoning_summary",
            status="completed",
            parent_item_id="item-1",
            content_redacted="推理摘要",
            summary_json={"source_channel": "reasoning_delta"},
            sensitive_level="internal",
        )
        db.session.add(item)
        db.session.flush()
        payload = item.to_dict()
        assert payload["item_type"] == "reasoning_summary"
        assert payload["sensitive_level"] == "internal"
        assert payload["summary"]["source_channel"] == "reasoning_delta"
        reloaded = db.session.get(AgentItem, item.id)
        assert reloaded.public_id == "item-2"
        assert reloaded.created_at is not None
        assert reloaded.started_at is None
        reloaded.started_at = item.created_at
        reloaded.completed_at = item.created_at
        db.session.commit()


def test_control_input_run_scoped_client_request_unique(app):
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentControlInput(
                public_id="ctl-1",
                run_id=run.id,
                input_type="user_message",
                client_request_id="req-1",
                status="pending",
            )
        )
        db.session.flush()
        db.session.add(
            AgentControlInput(
                public_id="ctl-2",
                run_id=run.id,
                input_type="user_message",
                client_request_id="req-1",
                status="pending",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        other = _make_run()
        db.session.add(
            AgentControlInput(
                public_id="ctl-3",
                run_id=other.id,
                input_type="user_message",
                client_request_id="req-1",
                status="pending",
            )
        )
        db.session.commit()


def test_conversation_summary_version_unique(app):
    with app.app_context():
        db.session.add(
            AgentConversationSummary(
                conversation_id=1,
                summary_version=1,
                source_sequence_from=1,
                source_sequence_to=10,
                summary_json={},
                content_digest="abc",
            )
        )
        db.session.flush()
        db.session.add(
            AgentConversationSummary(
                conversation_id=1,
                summary_version=1,
                source_sequence_from=11,
                source_sequence_to=20,
                summary_json={},
                content_digest="def",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_agent_events_run_sequence_unique(app):
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=1,
                state_version=0,
                event_type="run.created",
            )
        )
        db.session.flush()
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=1,
                state_version=0,
                event_type="run.created",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_agent_events_extended_columns_writable(app):
    with app.app_context():
        run = _make_run()
        event = AgentEvent(
            run_id=run.id,
            sequence=1,
            state_version=0,
            event_type="item.reasoning_summary.delta",
            conversation_id=5,
            turn_id=8,
            iteration=2,
            item_public_id="item-9",
            parent_item_public_id="item-1",
            dedupe_key="d-1",
        )
        db.session.add(event)
        db.session.commit()
        reloaded = db.session.get(AgentEvent, event.id)
        assert reloaded.item_public_id == "item-9"
        assert reloaded.parent_item_public_id == "item-1"
        assert reloaded.dedupe_key == "d-1"
        assert reloaded.iteration == 2


def test_agent_runs_extended_columns_writable(app):
    with app.app_context():
        run = _make_run()
        run.iteration_count = 7
        run.max_iterations = 20
        run.current_item_public_id = "item-9"
        run.policy_snapshot_json = {"run_mode": "hybrid"}
        run.tool_catalog_digest = "sha256:abc"
        run.context_watermark = 42
        run.last_checkpoint_id = 3
        db.session.commit()
        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.iteration_count == 7
        assert reloaded.max_iterations == 20
        assert reloaded.current_item_public_id == "item-9"
        assert reloaded.policy_snapshot_json["run_mode"] == "hybrid"
        assert reloaded.tool_catalog_digest == "sha256:abc"
        assert reloaded.context_watermark == 42
        assert reloaded.last_checkpoint_id == 3


def test_agent_tool_calls_extended_columns_writable(app):
    with app.app_context():
        run = _make_run()
        call = AgentToolCall(
            run_id=run.id,
            tool_name="read_code_slice",
            idempotency_key="k-1",
            provider_call_id="p-1",
            logical_call_key="l-1",
            attempt_number=1,
            arguments_digest="digest-1",
            result_schema_version=1,
            retryable=False,
            item_public_id="item-10",
        )
        db.session.add(call)
        db.session.commit()
        reloaded = db.session.get(AgentToolCall, call.id)
        assert reloaded.provider_call_id == "p-1"
        assert reloaded.logical_call_key == "l-1"
        assert reloaded.attempt_number == 1
        assert reloaded.arguments_digest == "digest-1"
        assert reloaded.result_schema_version == 1
        assert reloaded.retryable is False
        assert reloaded.item_public_id == "item-10"


def test_agent_checkpoints_extended_columns_writable(app):
    with app.app_context():
        run = _make_run()
        checkpoint = AgentCheckpoint(
            run_id=run.id,
            plan_version=1,
            state_json={},
            event_sequence=5,
            iteration=2,
            context_watermark=5,
            current_item_public_id="item-9",
            lease_owner="worker-1",
            checkpoint_digest="sha256:x",
        )
        db.session.add(checkpoint)
        db.session.commit()
        reloaded = db.session.get(AgentCheckpoint, checkpoint.id)
        assert reloaded.iteration == 2
        assert reloaded.context_watermark == 5
        assert reloaded.current_item_public_id == "item-9"
        assert reloaded.lease_owner == "worker-1"
        assert reloaded.checkpoint_digest == "sha256:x"


def test_legacy_run_and_message_still_readable(app):
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentMessage(
                run_id=run.id,
                role="user",
                content="旧消息",
                message_type="user_goal",
            )
        )
        db.session.commit()
        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.goal_text == "测试目标"
        messages = AgentMessage.query.filter_by(run_id=run.id).all()
        assert len(messages) == 1
        assert messages[0].message_type == "user_goal"
