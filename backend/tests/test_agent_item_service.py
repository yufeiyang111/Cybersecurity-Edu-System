# -*- coding: utf-8 -*-
"""T03 ItemService 生命周期与回滚测试（started → delta* → completed|failed）。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_items import AgentItem
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.timeline.item_service import ItemService, ItemStateError


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


def _events_of(run_id: int) -> list[AgentEvent]:
    return (
        AgentEvent.query.filter_by(run_id=run_id)
        .order_by(AgentEvent.sequence.asc())
        .all()
    )


def test_item_lifecycle_start_delta_complete(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())

        item, started = service.start(
            run,
            public_id="reason-1",
            item_type="reasoning_summary",
            event_type="item.reasoning_summary.started",
            iteration=1,
            sensitive_level="internal",
            trace_id="t-1",
        )
        assert item.status == "started"

        item, delta_1 = service.append_delta(
            run,
            "reason-1",
            delta="先核对扫描证据。",
            event_type="item.reasoning_summary.delta",
            trace_id="t-1",
        )
        item, delta_2 = service.append_delta(
            run,
            "reason-1",
            delta="再按调用链定位入口。",
            event_type="item.reasoning_summary.delta",
            trace_id="t-1",
        )
        item, completed = service.complete(
            run,
            "reason-1",
            content=None,
            summary_json={"source_channel": "reasoning_delta"},
            event_type="item.reasoning_summary.completed",
            trace_id="t-1",
        )
        assert item.status == "completed"
        assert item.completed_at is not None
        assert item.content_redacted == "先核对扫描证据。再按调用链定位入口。"

        sequences = [event.sequence for event in _events_of(run.id)]
        assert sequences == sorted(sequences)
        assert [event.event_type for event in _events_of(run.id)] == [
            "item.reasoning_summary.started",
            "item.reasoning_summary.delta",
            "item.reasoning_summary.delta",
            "item.reasoning_summary.completed",
        ]


def test_item_terminal_state_rejects_delta(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="tool-1",
            item_type="tool_call",
            event_type="item.tool_call.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        service.complete(
            run,
            "tool-1",
            content="完成",
            event_type="item.tool_call.completed",
            trace_id="t-1",
        )
        with pytest.raises(ItemStateError):
            service.append_delta(
                run,
                "tool-1",
                delta="迟到增量",
                event_type="item.tool_call.arguments.delta",
                trace_id="t-1",
            )


def test_item_start_idempotent_on_dedupe_key(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        item_a, _ = service.start(
            run,
            public_id="msg-1",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            dedupe_key="dedupe-1",
            trace_id="t-1",
        )
        item_b, event_b = service.start(
            run,
            public_id="msg-1",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            dedupe_key="dedupe-1",
            trace_id="t-1",
        )
        assert item_b.public_id == item_a.public_id
        assert event_b.dedupe_key == "dedupe-1"
        started_events = [
            event
            for event in _events_of(run.id)
            if event.event_type == "item.assistant_message.started"
        ]
        assert len(started_events) == 1, "重复 dedupe_key 不得重复写事件"


def test_parent_child_sequence_order(app):
    """Tool Result 不得先于 Tool Call；Assistant Message 必须在最后。"""
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        writer = EventWriter()

        service.start(
            run,
            public_id="toolcall-1",
            item_type="tool_call",
            event_type="item.tool_call.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        service.complete(
            run,
            "toolcall-1",
            content="读取完成",
            event_type="item.tool_call.completed",
            trace_id="t-1",
        )
        writer.emit(
            run,
            event_type="item.tool_result.created",
            item_id="toolresult-1",
            parent_item_id="toolcall-1",
            payload={"summary": "结果"},
            trace_id="t-1",
        )
        service.start(
            run,
            public_id="final-1",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        service.complete(
            run,
            "final-1",
            content="最终回答",
            event_type="item.assistant_message.completed",
            trace_id="t-1",
        )

        events = _events_of(run.id)
        by_type = {event.event_type: event.sequence for event in events}
        assert by_type["item.tool_call.completed"] < by_type["item.tool_result.created"]
        assert by_type["item.tool_result.created"] < by_type["item.assistant_message.started"]
        assert by_type["item.assistant_message.completed"] == max(
            by_type.values()
        )


def test_item_failed_state_and_rollback_no_orphan_event(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="tool-2",
            item_type="tool_call",
            event_type="item.tool_call.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        service.fail(
            run,
            "tool-2",
            error_code="AGENT_TOOL_FAILED",
            event_type="item.tool_call.failed",
            trace_id="t-1",
        )
        failed = db.session.get(AgentItem, run.id) if False else AgentItem.query.filter_by(
            run_id=run.id, public_id="tool-2"
        ).one()
        assert failed.status == "failed"

        db.session.rollback()
        events_after_rollback = _events_of(run.id)
        item_count = AgentItem.query.filter_by(run_id=run.id).count()
        assert item_count == 0
        assert events_after_rollback == []
