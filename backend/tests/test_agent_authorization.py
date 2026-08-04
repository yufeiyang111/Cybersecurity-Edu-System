"""Agent authorization negative tests: roles and cross-workspace isolation."""
from __future__ import annotations

from app import db
from app.models.security import WorkspaceMember
from app.services.workspaces import get_or_create_personal_workspace

from test_agent_run_api import (
    auth_headers,
    make_project_and_snapshot,
    make_user,
)


def test_viewer_cannot_create_run(agent_api_app, tmp_path):
    viewer_id, workspace_id = make_user(agent_api_app, "judy", "judy@example.test", role="viewer")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, viewer_id, workspace_id)
    client = agent_api_app.test_client()

    response = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点一下"},
        headers=auth_headers(agent_api_app, viewer_id),
    )
    assert response.status_code == 403


def test_viewer_can_read_run(agent_api_app, tmp_path):
    owner_id, workspace_id = make_user(agent_api_app, "kim", "kim@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, owner_id, workspace_id)
    client = agent_api_app.test_client()

    created = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点一下"},
        headers=auth_headers(agent_api_app, owner_id),
    )
    run_id = created.json["run"]["id"]

    viewer_id = make_user(agent_api_app, "leo", "leo@example.test", role="viewer")[0]
    with agent_api_app.app_context():
        viewer = WorkspaceMember(
            workspace_id=workspace_id, user_id=viewer_id, role="viewer"
        )
        db.session.add(viewer)
        db.session.commit()
        membership = WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=viewer_id).first()
        assert membership is not None

    detail = client.get(
        f"/api/security/agent-runs/{run_id}", headers=auth_headers(agent_api_app, viewer_id)
    )
    assert detail.status_code == 200

    denied = client.post(
        f"/api/security/agent-runs/{run_id}/pause", headers=auth_headers(agent_api_app, viewer_id)
    )
    assert denied.status_code == 403


def test_cross_workspace_run_is_invisible(agent_api_app, tmp_path):
    owner_id, workspace_id = make_user(agent_api_app, "mia", "mia@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, owner_id, workspace_id)
    client = agent_api_app.test_client()

    created = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点一下"},
        headers=auth_headers(agent_api_app, owner_id),
    )
    run_id = created.json["run"]["id"]

    outsider_id = make_user(agent_api_app, "nick", "nick@example.test")[0]
    outsider_workspace_id = get_or_create_personal_workspace(outsider_id).id
    assert outsider_workspace_id != workspace_id

    response = client.get(
        f"/api/security/agent-runs/{run_id}", headers=auth_headers(agent_api_app, outsider_id)
    )
    assert response.status_code == 403
