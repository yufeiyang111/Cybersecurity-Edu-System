# -*- coding: utf-8 -*-
"""T10 SSE v2 重连测试：Last-Event-ID 精确续传、Gap 检测、快照一致性、无泄露。"""
from __future__ import annotations

import json

from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter

from test_agent_sse_api import _stream_frames
from test_agent_run_api import (
    auth_headers,
    make_project_and_snapshot,
    make_user,
)


def _make_run_with_events(agent_api_app, tmp_path, *, user_label="v2sse"):
    user_id, workspace_id = make_user(
        agent_api_app, user_label, f"{user_label}@example.test"
    )
    project_id, _ = make_project_and_snapshot(
        agent_api_app, tmp_path, user_id, workspace_id
    )
    with agent_api_app.app_context():
        from app.models.agent_runtime import AgentRunStatus

        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=1,
            created_by=user_id,
            goal_text="SSE v2 测试",
            mode="hybrid",
            status=AgentRunStatus.COMPLETED.value,
        )
        db.session.add(run)
        db.session.flush()
        writer = EventWriter()
        writer.emit(
            run,
            event_type="item.user_message.created",
            item_id="msg-1",
            payload={"content": "检查越权"},
            trace_id="t-1",
        )
        writer.emit(
            run,
            event_type="item.reasoning_summary.started",
            item_id="rs-1",
            payload={"sensitive_level": "internal"},
            trace_id="t-1",
        )
        writer.emit(
            run,
            event_type="item.reasoning_summary.delta",
            item_id="rs-1",
            payload={"delta": "先核对证据", "sensitive_level": "internal"},
            trace_id="t-1",
        )
        db.session.commit()
        return run.id, user_id


def test_sse_v2_replays_exactly_after_last_event_id(agent_api_app, tmp_path):
    run_id, user_id = _make_run_with_events(agent_api_app, tmp_path)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    first = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream", headers=headers
    )
    first_frames = _stream_frames(first)
    ids = [frame["id"] for frame in first_frames if "id" in frame]
    assert ids == [1, 2, 3]

    replay_headers = dict(headers)
    replay_headers["Last-Event-ID"] = "2"
    replay = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream",
        headers=replay_headers,
    )
    replay_frames = _stream_frames(replay)
    replay_ids = [frame["id"] for frame in replay_frames if "id" in frame]
    assert replay_ids == [3], "Last-Event-ID 之后必须精确续传，无漏无重"
    assert replay_frames[0]["event"] == "item.reasoning_summary.delta"
    assert replay_frames[0]["data"]["sequence"] == 3


def test_sse_v2_replay_gap_returns_error_frame(agent_api_app, tmp_path):
    run_id, user_id = _make_run_with_events(agent_api_app, tmp_path, user_label="gap1")
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    with agent_api_app.app_context():
        from app.models.agent_events import AgentEvent

        oldest = (
            AgentEvent.query.filter_by(run_id=run_id)
            .order_by(AgentEvent.sequence.asc())
            .first()
        )
        assert oldest.sequence == 1
        # 模拟历史归档：删除最早事件，客户端水位 0 落后于归档边界
        db.session.delete(oldest)
        db.session.commit()
        gap_headers = dict(headers)
        gap_headers["Last-Event-ID"] = "0"
        response = client.get(
            f"/api/security/agent-runs/{run_id}/events/stream",
            headers=gap_headers,
        )
        frames = _stream_frames(response)
        error_frames = [frame for frame in frames if frame.get("event") == "error"]
        assert error_frames, "水位过旧必须返回 AGENT_SSE_REPLAY_GAP"
        assert error_frames[0]["data"]["code"] == "AGENT_SSE_REPLAY_GAP"


def test_snapshot_text_matches_stream_accumulation(agent_api_app, tmp_path):
    """完成后 Snapshot 的 assistant 文本与流 delta 累计逐字一致。"""
    run_id, user_id = _make_run_with_events(agent_api_app, tmp_path, user_label="snap1")
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    with agent_api_app.app_context():
        from app.services.security_agent.timeline.item_service import ItemService

        run = db.session.get(AgentRun, run_id)
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-final",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-snap",
        )
        service.append_delta(
            run,
            "asst-final",
            delta="审查完成：",
            event_type="item.assistant_message.delta",
            trace_id="t-snap",
        )
        service.append_delta(
            run,
            "asst-final",
            delta="鉴权链路存在越权风险。",
            event_type="item.assistant_message.delta",
            trace_id="t-snap",
        )
        service.complete(
            run,
            "asst-final",
            event_type="item.assistant_message.completed",
            trace_id="t-snap",
        )
        db.session.commit()

    snapshot = client.get(
        f"/api/security/agent-runs/{run_id}", headers=headers
    ).get_json()
    assert snapshot["snapshot_watermark"] == snapshot["last_sequence"]
    items = snapshot["items"]
    assistant = next(
        item for item in items if item["public_id"] == "asst-final"
    )
    stream_frames = _stream_frames(
        client.get(
            f"/api/security/agent-runs/{run_id}/events/stream", headers=headers
        )
    )
    accumulated = "".join(
        frame["data"]["payload"].get("delta", "")
        for frame in stream_frames
        if frame.get("event") == "item.assistant_message.delta"
    )
    assert assistant["content"] == accumulated == "审查完成：鉴权链路存在越权风险。"


def test_sse_v2_payload_has_no_sensitive_content(agent_api_app, tmp_path):
    run_id, user_id = _make_run_with_events(agent_api_app, tmp_path, user_label="safe1")
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)
    response = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream", headers=headers
    )
    raw = "".join(
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in response.response
    )
    assert "Bearer " not in raw
    assert "sk-" not in raw
    assert "Traceback" not in raw
    assert "reasoning_full" not in raw
