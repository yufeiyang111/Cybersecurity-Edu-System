# -*- coding: utf-8 -*-
"""T03 Snapshot 一致性测试：固定水位、单调递增、v1 legacy 兼容。"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_items import AgentItem
from app.models.agent_runtime import AgentMessage, AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.timeline.item_service import ItemService
from app.services.security_agent.timeline.serializers import (
    legacy_item_from_event,
    legacy_item_from_message,
)
from app.services.security_agent.timeline.snapshot_service import SnapshotService


def _make_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="快照测试",
        mode="hybrid",
    )
    db.session.add(run)
    db.session.flush()
    return run


def _write_reasoning_item(run: AgentRun) -> None:
    service = ItemService(EventWriter())
    service.start(
        run,
        public_id="rs-1",
        item_type="reasoning_summary",
        event_type="item.reasoning_summary.started",
        sensitive_level="internal",
        trace_id="snap-1",
    )
    service.append_delta(
        run,
        "rs-1",
        delta="先核对扫描证据。",
        event_type="item.reasoning_summary.delta",
        trace_id="snap-1",
    )
    service.complete(
        run,
        "rs-1",
        summary_json={"source_channel": "reasoning_delta"},
        event_type="item.reasoning_summary.completed",
        trace_id="snap-1",
    )


def test_snapshot_all_content_within_watermark(app):
    with app.app_context():
        run = _make_run()
        _write_reasoning_item(run)
        EventWriter().emit(
            run,
            event_type="item.observation.created",
            item_id="obs-1",
            payload={"summary": "观察"},
            trace_id="snap-1",
        )
        db.session.commit()

        snapshot = SnapshotService().build_snapshot(run.id)
        watermark = snapshot["snapshot_watermark"]
        assert watermark == run.last_event_sequence
        for event in snapshot["events"]:
            assert event["sequence"] <= watermark
        for item in snapshot["items"]:
            assert item["public_id"] in {"rs-1"}
        assert snapshot["run"]["goal_text"] == "快照测试"
        assert snapshot["plan"] is None


def test_snapshot_watermark_monotonic_increasing(app):
    with app.app_context():
        run = _make_run()
        _write_reasoning_item(run)
        db.session.commit()
        first = SnapshotService().build_snapshot(run.id)
        watermark_1 = first["snapshot_watermark"]

        EventWriter().emit(
            run,
            event_type="warning.raised",
            payload={"warning_codes": ["AGENT_PARTIAL_RESULT"]},
            trace_id="snap-2",
        )
        db.session.commit()
        second = SnapshotService().build_snapshot(run.id)
        watermark_2 = second["snapshot_watermark"]
        assert watermark_2 > watermark_1
        assert watermark_2 == run.last_event_sequence
        assert len(second["events"]) == len(first["events"]) + 1


def test_snapshot_unchanged_without_new_events(app):
    with app.app_context():
        run = _make_run()
        _write_reasoning_item(run)
        db.session.commit()
        first = SnapshotService().build_snapshot(run.id)
        second = SnapshotService().build_snapshot(run.id)
        assert first["snapshot_watermark"] == second["snapshot_watermark"]
        assert first["items"] == second["items"]
        assert first["events"] == second["events"]


def test_legacy_message_converted_without_faking_v2_order(app):
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentMessage(
                run_id=run.id,
                role="agent",
                content="旧分析",
                message_type="llm_analysis",
            )
        )
        db.session.flush()
        legacy = legacy_item_from_message(
            AgentMessage.query.filter_by(run_id=run.id).one()
        )
        assert legacy["schema_version"] == 1
        assert legacy["item_type"] == "assistant_message"
        assert legacy["status"] == "completed"
        assert legacy["content"] == "旧分析"
        assert legacy["source"] == "legacy_message"


def test_legacy_event_converted_with_original_sequence(app):
    with app.app_context():
        run = _make_run()
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=7,
                state_version=2,
                event_type="plan.created",
                payload_json={"plan_version": 1},
            )
        )
        db.session.flush()
        legacy = legacy_item_from_event(
            AgentEvent.query.filter_by(run_id=run.id).one()
        )
        assert legacy["schema_version"] == 1
        assert legacy["sequence"] == 7
        assert legacy["source"] == "legacy_event"


def test_items_pagination_query_service_level(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        for index in range(5):
            service.start(
                run,
                public_id=f"item-{index}",
                item_type="tool_call",
                event_type="item.tool_call.started",
                sensitive_level="internal",
                trace_id="page-1",
            )
            db.session.commit()

        items, total = SnapshotService().list_items(
            run.id, page_size=2, page=1
        )
        assert total == 5
        assert len(items) == 2
        assert items[0].public_id == "item-0"
        page_2, _ = SnapshotService().list_items(run.id, page_size=2, page=3)
        assert [item.public_id for item in page_2] == ["item-4"]
