# -*- coding: utf-8 -*-
"""T10 SSE Heartbeat v2 测试：正式 heartbeat 事件、不进时间线、terminal 关闭。"""
from __future__ import annotations

from app.services.security_agent.sse import heartbeat_frame

from test_agent_sse_api import _stream_frames
from test_agent_run_api import auth_headers, make_project_and_snapshot, make_user


def test_heartbeat_frame_is_formal_event_without_id():
    """心跳必须是正式事件（event: heartbeat），不携带 id 以免占用 sequence。"""
    frame = heartbeat_frame(sequence=12)
    assert frame.startswith("event: heartbeat\n")
    assert "\nid:" not in frame
    assert '"sequence": 12' in frame


def test_heartbeat_frame_is_parseable_by_client_parser():
    """前端 parser 能识别 heartbeat 帧并刷新健康定时器。"""
    raw = heartbeat_frame(sequence=3)
    parsed = {"event": None, "data": None}
    for line in raw.split("\n"):
        if line.startswith("event:"):
            parsed["event"] = line[6:].strip()
        elif line.startswith("data:"):
            import json

            parsed["data"] = json.loads(line[5:].strip())
    assert parsed["event"] == "heartbeat"
    assert parsed["data"]["sequence"] == 3


def test_heartbeat_never_enters_timeline_semantics():
    """heartbeat 不改变 reducer 的 lastSequence（无 id 帧被 reducer 忽略）。"""
    raw = heartbeat_frame(sequence=5)
    assert "\nid:" not in raw
    assert "event: heartbeat" in raw


def test_terminal_stream_closes_without_heartbeat_loop(agent_api_app, tmp_path):
    """终态且追平后流关闭；心跳只在长连接无事件时出现。"""
    user_id, workspace_id = make_user(agent_api_app, "beat1", "beat1@example.test")
    project_id, _ = make_project_and_snapshot(
        agent_api_app, tmp_path, user_id, workspace_id
    )
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)
    created = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点一下"},
        headers=headers,
    )
    run_id = created.json["run"]["id"]
    response = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream", headers=headers
    )
    frames = _stream_frames(response)
    assert frames, "流必须返回事件"
    heartbeat_frames = [
        frame for frame in frames if frame.get("event") == "heartbeat"
    ]
    assert heartbeat_frames == [], "短生命周期测试流不应出现 heartbeat"
    last = frames[-1]
    assert last["data"]["run_id"] == run_id
    assert last["data"]["sequence"] == last["id"]
