"""Multi-turn conversation API tests: create, idempotent messages, turn+run reuse."""
from __future__ import annotations

import uuid

from app import db
from app.models.agent_runtime import AgentRun
from app.models.conversation import AgentConversation, AgentConversationMessage, AgentTurn
from app.models.security import ProjectSnapshot, ScanTask, SecurityProject
from app.models.user import User
from app.services.workspaces import get_or_create_personal_workspace

from test_agent_run_api import (
    auth_headers,
    make_project_and_snapshot,
    make_user,
)


def _new_client_id() -> str:
    return uuid.uuid4().hex


def test_create_conversation_and_first_message_creates_run(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv1", "conv1@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    created = client.post(
        f"/api/security/projects/{project_id}/agent-conversations",
        json={},
        headers=headers,
    )
    assert created.status_code == 201
    conversation_id = created.json["conversation"]["id"]

    first = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "先清点项目文件", "client_message_id": _new_client_id()},
        headers=headers,
    )
    assert first.status_code == 201
    body = first.json
    assert body["replayed"] is False
    assert body["message"]["message_sequence"] == 1
    assert body["message"]["content_digest"]
    assert body["turn"]["turn_sequence"] == 1
    assert body["run"]["status"] in {"completed", "executing_tools"}
    assert body["run"]["snapshot_id"] == snapshot_id
    run_id = body["run"]["id"]

    with agent_api_app.app_context():
        turn = db.session.get(AgentTurn, body["turn"]["id"])
        assert turn.run_id == run_id
        assert turn.conversation_id == conversation_id
        conversation = db.session.get(AgentConversation, conversation_id)
        assert conversation.current_snapshot_id == snapshot_id
        assert conversation.turn_sequence == 1
        assert conversation.message_sequence == 1
        assert conversation.title == "先清点项目文件"


def test_project_conversations_are_listed_newest_first(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv-list", "conv-list@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    older = client.post(
        f"/api/security/projects/{project_id}/agent-conversations",
        json={"title": "旧会话"},
        headers=headers,
    )
    newer = client.post(
        f"/api/security/projects/{project_id}/agent-conversations",
        json={"title": "新会话"},
        headers=headers,
    )
    assert older.status_code == 201
    assert newer.status_code == 201

    response = client.get(
        f"/api/security/projects/{project_id}/agent-conversations?page=1&page_size=1",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json
    assert body["pagination"] == {"total": 2, "page": 1, "page_size": 1}
    assert body["items"][0]["id"] == newer.json["conversation"]["id"]

    outsider_id = make_user(agent_api_app, "conv-list-outsider", "conv-list-outsider@example.test")[0]
    denied = client.get(
        f"/api/security/projects/{project_id}/agent-conversations",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert denied.status_code == 403


def test_second_turn_reuses_snapshot_without_reupload(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv2", "conv2@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    conversation_id = client.post(
        f"/api/security/projects/{project_id}/agent-conversations", json={}, headers=headers
    ).json["conversation"]["id"]
    first = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "第一轮：全量扫描", "client_message_id": _new_client_id()},
        headers=headers,
    ).json
    first_run_id = first["run"]["id"]

    second = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "第二轮：只查看后端配置", "client_message_id": _new_client_id()},
        headers=headers,
    )
    assert second.status_code == 201
    body = second.json
    assert body["turn"]["turn_sequence"] == 2
    assert body["message"]["message_sequence"] == 2
    assert body["message"]["message_type"] == "follow_up"
    assert body["run"]["snapshot_id"] == snapshot_id, "第二轮必须复用同一快照"
    assert body["run"]["id"] != first_run_id, "第二轮创建新 Run，不覆盖旧 Run"

    with agent_api_app.app_context():
        turn = db.session.get(AgentTurn, body["turn"]["id"])
        assert turn.parent_turn_id is not None
        assert db.session.get(AgentRun, first_run_id) is not None, "旧 Run 保留"


def test_duplicate_client_message_id_is_idempotent(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv3", "conv3@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)
    conversation_id = client.post(
        f"/api/security/projects/{project_id}/agent-conversations", json={}, headers=headers
    ).json["conversation"]["id"]
    client_message_id = _new_client_id()

    first = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "幂等测试", "client_message_id": client_message_id},
        headers=headers,
    )
    second = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "幂等测试", "client_message_id": client_message_id},
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json["replayed"] is True
    assert second.json["message"]["id"] == first.json["message"]["id"]

    with agent_api_app.app_context():
        assert AgentConversationMessage.query.filter_by(
            client_message_id=client_message_id
        ).count() == 1
        assert AgentRun.query.count() == 1, "重复提交不得重复创建 Run"
        assert AgentTurn.query.count() == 1


def test_messages_are_paginated(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv4", "conv4@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)
    conversation_id = client.post(
        f"/api/security/projects/{project_id}/agent-conversations", json={}, headers=headers
    ).json["conversation"]["id"]
    for index in range(3):
        client.post(
            f"/api/security/agent-conversations/{conversation_id}/messages",
            json={"content": f"消息 {index}", "client_message_id": _new_client_id()},
            headers=headers,
        )

    page = client.get(
        f"/api/security/agent-conversations/{conversation_id}/messages?page=1&page_size=2",
        headers=headers,
    )
    assert page.status_code == 200
    body = page.json
    assert body["pagination"]["total"] == 3
    assert len(body["items"]) == 2
    assert [item["message_sequence"] for item in body["items"]] == [1, 2]

    page2 = client.get(
        f"/api/security/agent-conversations/{conversation_id}/messages?page=2&page_size=2",
        headers=headers,
    )
    assert [item["message_sequence"] for item in page2.json["items"]] == [3]


def test_conversation_requires_workspace_membership(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv5", "conv5@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    outsider_id = make_user(agent_api_app, "conv6", "conv6@example.test")[0]
    client = agent_api_app.test_client()
    conversation_id = client.post(
        f"/api/security/projects/{project_id}/agent-conversations", json={}, headers=auth_headers(agent_api_app, user_id)
    ).json["conversation"]["id"]

    denied = client.get(
        f"/api/security/agent-conversations/{conversation_id}",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert denied.status_code == 403

    denied_post = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "越权", "client_message_id": _new_client_id()},
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert denied_post.status_code == 403


def test_invalid_client_message_id_rejected(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "conv7", "conv7@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)
    conversation_id = client.post(
        f"/api/security/projects/{project_id}/agent-conversations", json={}, headers=headers
    ).json["conversation"]["id"]

    response = client.post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        json={"content": "非法 id", "client_message_id": "bad id!"},
        headers=headers,
    )
    assert response.status_code == 400
