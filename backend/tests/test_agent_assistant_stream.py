# -*- coding: utf-8 -*-
"""T10 Assistant Message 增量流测试：started → delta* → completed 冻结。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_items import AgentItem
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.timeline.item_service import (
    ItemService,
    ItemStateError,
)


@pytest.fixture(autouse=True)
def _enable_v2_event_schema(app):
    """本文件验证 v2 事件协议：显式开启 Event v2 flag（S-03）。"""
    app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
    yield


def _make_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="最终回答流测试",
        mode="hybrid",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_assistant_message_stream_start_deltas_completed(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-1",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        for delta in ("审查完成：", "发现 3 个高风险项，", "证据见引用。"):
            service.append_delta(
                run,
                "asst-1",
                delta=delta,
                event_type="item.assistant_message.delta",
                trace_id="t-1",
            )
        service.complete(
            run,
            "asst-1",
            event_type="item.assistant_message.completed",
            trace_id="t-1",
        )

        events = (
            AgentEvent.query.filter_by(run_id=run.id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        assert [event.event_type for event in events] == [
            "item.assistant_message.started",
            "item.assistant_message.delta",
            "item.assistant_message.delta",
            "item.assistant_message.delta",
            "item.assistant_message.completed",
        ]
        assert len({event.item_public_id for event in events}) == 1, "delta 必须更新同一 item"

        item = AgentItem.query.filter_by(run_id=run.id, public_id="asst-1").one()
        assert item.status == "completed"
        assert item.completed_at is not None
        assert item.content_redacted == "审查完成：发现 3 个高风险项，证据见引用。"
        assert item.content_redacted == "".join(
            event.payload_json.get("delta", "")
            for event in events
            if event.event_type == "item.assistant_message.delta"
        ), "刷新恢复文本必须与流累计逐字一致"


def test_assistant_message_terminal_frozen_rejects_delta(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-2",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        service.complete(
            run,
            "asst-2",
            content="冻结内容",
            event_type="item.assistant_message.completed",
            trace_id="t-1",
        )
        with pytest.raises(ItemStateError):
            service.append_delta(
                run,
                "asst-2",
                delta="迟到增量",
                event_type="item.assistant_message.delta",
                trace_id="t-1",
            )
        item = AgentItem.query.filter_by(run_id=run.id, public_id="asst-2").one()
        assert item.content_redacted == "冻结内容"


def test_assistant_message_delta_size_capped(app):
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-3",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        with pytest.raises(ItemStateError):
            service.append_delta(
                run,
                "asst-3",
                delta="x" * (ItemService.MAX_DELTA_CHARS + 1),
                event_type="item.assistant_message.delta",
                trace_id="t-1",
            )
        item = AgentItem.query.filter_by(run_id=run.id, public_id="asst-3").one()
        assert item.content_redacted is None or item.content_redacted == ""


def test_assistant_message_failed_never_completes_run(app):
    """Final Assistant Item 失败时 Run 不进入 completed（由 Evaluator 判定）。"""
    with app.app_context():
        run = _make_run()
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-4",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-1",
        )
        service.fail(
            run,
            "asst-4",
            error_code="AGENT_ASSISTANT_STREAM_FAILED",
            event_type="item.assistant_message.failed",
            trace_id="t-1",
        )
        item = AgentItem.query.filter_by(run_id=run.id, public_id="asst-4").one()
        assert item.status == "failed"
        assert item.summary_json.get("error_code") == "AGENT_ASSISTANT_STREAM_FAILED"
