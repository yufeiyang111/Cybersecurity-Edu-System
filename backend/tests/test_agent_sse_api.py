"""SSE stream API tests: replay, Last-Event-ID, terminal close, format."""
from __future__ import annotations

import json

from flask_jwt_extended import create_access_token

from app import db
from app.models.security import ProjectSnapshot, SecurityProject
from app.models.user import User
from app.services.workspaces import get_or_create_personal_workspace

from test_agent_run_api import (
    auth_headers,
    make_project_and_snapshot,
    make_user,
)


def _stream_frames(response):
    """Collect SSE frames from a test client streaming response."""
    frames = []
    for chunk in response.response:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            frame = {}
            for line in block.split("\n"):
                if line.startswith("id:"):
                    frame["id"] = int(line[3:].strip())
                elif line.startswith("event:"):
                    frame["event"] = line[6:].strip()
                elif line.startswith("data:"):
                    frame["data"] = json.loads(line[5:].strip())
                elif line.startswith(":"):
                    frame["comment"] = line[1:].strip()
            if frame:
                frames.append(frame)
    return frames


def test_stream_replays_events_and_closes_on_terminal_run(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "frank", "frank@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
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

    assert frames, "流应该返回事件帧"
    sequences = [frame["id"] for frame in frames if "id" in frame]
    assert sequences == sorted(sequences), "sequence 必须单调递增"
    assert sequences == list(range(1, len(sequences) + 1)), "sequence 必须从 1 连续递增"

    event_names = [frame["event"] for frame in frames if "event" in frame]
    assert "run.created" in event_names
    assert "tool.completed" in event_names
    assert "run.completed" in event_names

    last = frames[-1]
    assert last["data"]["run_id"] == run_id
    assert last["data"]["sequence"] == last["id"]


def test_last_event_id_replays_only_missing_events(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "grace", "grace@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    created = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点一下"},
        headers=headers,
    )
    run_id = created.json["run"]["id"]

    first_stream = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream", headers=headers
    )
    first_frames = _stream_frames(first_stream)
    last_sequence = first_frames[-1]["id"]

    replay_headers = dict(headers)
    replay_headers["Last-Event-ID"] = str(last_sequence)
    replay = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream", headers=replay_headers
    )
    replay_frames = _stream_frames(replay)
    assert replay_frames == [], "已终止且追平的事件流不应再返回任何事件"


def test_stream_requires_workspace_membership(agent_api_app, tmp_path):
    owner_id, workspace_id = make_user(agent_api_app, "heidi", "heidi@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, owner_id, workspace_id)
    client = agent_api_app.test_client()

    created = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点一下"},
        headers=auth_headers(agent_api_app, owner_id),
    )
    run_id = created.json["run"]["id"]

    outsider_id = make_user(agent_api_app, "ivan", "ivan@example.test")[0]
    response = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert response.status_code == 403
