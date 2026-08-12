# -*- coding: utf-8 -*-
"""T13 重放端到端测试：Snapshot/SSE/Item 在任意水位一致，刷新可复现。"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
)
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.timeline.item_service import ItemService
from app.services.security_agent.timeline.snapshot_service import SnapshotService


def _make_run(app):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="重放测试",
            mode="hybrid",
            status=AgentRunStatus.COMPLETED.value,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="重放测试",
        )
        db.session.add(plan)
        db.session.flush()
        db.session.commit()
        return run.id


def test_replay_snapshot_consistent_at_any_watermark(app):
    run_id = _make_run(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-1",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-r1",
        )
        service.append_delta(
            run,
            "asst-1",
            delta="第一段。",
            event_type="item.assistant_message.delta",
            trace_id="t-r1",
        )
        db.session.commit()
        mid = SnapshotService().build_snapshot(run_id)
        assert mid["snapshot_watermark"] == run.last_event_sequence
        for event in mid["events"]:
            assert event["sequence"] <= mid["snapshot_watermark"]
        item = mid["items"][0]
        assert item["content"] == "第一段。"

        service.append_delta(
            run,
            "asst-1",
            delta="第二段。",
            event_type="item.assistant_message.delta",
            trace_id="t-r1",
        )
        service.complete(
            run,
            "asst-1",
            event_type="item.assistant_message.completed",
            trace_id="t-r1",
        )
        db.session.commit()
        final = SnapshotService().build_snapshot(run_id)
        assert final["snapshot_watermark"] > mid["snapshot_watermark"]
        assert final["items"][0]["content"] == "第一段。第二段。"
        assert final["items"][0]["status"] == "completed"


def test_replay_deltas_reconstruct_exact_text(app):
    run_id = _make_run(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        service = ItemService(EventWriter())
        deltas = ["审查完成：", "发现 3 个高风险项。", "证据见引用。[OK]"]
        service.start(
            run,
            public_id="asst-2",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-r2",
        )
        for delta in deltas:
            service.append_delta(
                run,
                "asst-2",
                delta=delta,
                event_type="item.assistant_message.delta",
                trace_id="t-r2",
            )
        service.complete(
            run,
            "asst-2",
            event_type="item.assistant_message.completed",
            trace_id="t-r2",
        )
        db.session.commit()

        events = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        from_db = "".join(
            event.payload_json.get("delta", "")
            for event in events
            if event.event_type == "item.assistant_message.delta"
        )
        assert from_db == "".join(deltas)
        snapshot = SnapshotService().build_snapshot(run_id)
        assert snapshot["items"][0]["content"] == from_db
