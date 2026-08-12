# -*- coding: utf-8 -*-
"""T12 v2 鉴权测试：跨 workspace 访问 items/control-inputs/SSE 全部拒绝。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter

from test_agent_run_api import (
    auth_headers,
    make_project_and_snapshot,
    make_user,
)


def _make_run_with_events(agent_api_app, tmp_path, *, label="authv2"):
    user_id, workspace_id = make_user(agent_api_app, label, f"{label}@t")
    project_id, _ = make_project_and_snapshot(
        agent_api_app, tmp_path, user_id, workspace_id
    )
    with agent_api_app.app_context():
        from app.models.agent_runtime import AgentRunStatus
        from app.services.security_agent.timeline.item_service import ItemService

        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=1,
            created_by=user_id,
            goal_text="鉴权 v2",
            mode="hybrid",
            status=AgentRunStatus.EXECUTING_TOOLS.value,
        )
        db.session.add(run)
        db.session.flush()
        ItemService().start(
            run,
            public_id="msg-1",
            item_type="user_message",
            event_type="item.user_message.created",
            sensitive_level="internal",
            trace_id="t-auth",
        )
        db.session.commit()
        return run.id, user_id


def test_items_endpoint_requires_membership(agent_api_app, tmp_path):
    run_id, owner_id = _make_run_with_events(agent_api_app, tmp_path, label="items1")
    outsider_id, _ = make_user(agent_api_app, "items-outsider", "items-outsider@t")
    client = agent_api_app.test_client()
    response = client.get(
        f"/api/security/agent-runs/{run_id}/items",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert response.status_code == 403
    owned = client.get(
        f"/api/security/agent-runs/{run_id}/items",
        headers=auth_headers(agent_api_app, owner_id),
    )
    assert owned.status_code == 200
    assert owned.get_json()["pagination"]["total"] >= 1


def test_control_inputs_endpoint_requires_membership(agent_api_app, tmp_path):
    run_id, owner_id = _make_run_with_events(agent_api_app, tmp_path, label="ctl1")
    outsider_id, _ = make_user(agent_api_app, "ctl-outsider", "ctl-outsider@t")
    client = agent_api_app.test_client()
    response = client.post(
        f"/api/security/agent-runs/{run_id}/control-inputs",
        headers=auth_headers(agent_api_app, outsider_id),
        json={
            "client_request_id": "req-x",
            "type": "user_message",
            "payload": {"content": "越权尝试"},
        },
    )
    assert response.status_code == 403


def test_sse_stream_requires_membership(agent_api_app, tmp_path):
    run_id, _ = _make_run_with_events(agent_api_app, tmp_path, label="sseauth")
    outsider_id, _ = make_user(agent_api_app, "sse-outsider", "sse-outsider@t")
    client = agent_api_app.test_client()
    response = client.get(
        f"/api/security/agent-runs/{run_id}/events/stream",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert response.status_code == 403


def test_run_snapshot_requires_membership(agent_api_app, tmp_path):
    run_id, _ = _make_run_with_events(agent_api_app, tmp_path, label="snapauth")
    outsider_id, _ = make_user(agent_api_app, "snap-outsider", "snap-outsider@t")
    client = agent_api_app.test_client()
    response = client.get(
        f"/api/security/agent-runs/{run_id}",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert response.status_code == 403
