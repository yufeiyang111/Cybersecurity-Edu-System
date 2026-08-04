"""Agent run API tests: create, detail, pause/resume/cancel, event listing."""
from __future__ import annotations

from pathlib import Path

import pytest
from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.workspaces import get_or_create_personal_workspace


def make_user(application, username, email, role="owner"):
    with application.app_context():
        user = User(username=username, email=email, password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = get_or_create_personal_workspace(user.id)
        member = WorkspaceMember.query.filter_by(workspace_id=workspace.id, user_id=user.id).first()
        member.role = role
        db.session.commit()
        return user.id, workspace.id


def auth_headers(application, user_id):
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def make_project_and_snapshot(application, tmp_path, user_id, workspace_id):
    with application.app_context():
        project = SecurityProject(workspace_id=workspace_id, name="demo", created_by=user_id)
        db.session.add(project)
        db.session.flush()
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "app.py").write_text("import subprocess\n", encoding="utf-8")
        src_dir = snapshot_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "index.ts").write_text("const x = 1;\n", encoding="utf-8")
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="abc123",
            storage_path=str(snapshot_dir),
            file_count=2,
            total_bytes=30,
        )
        db.session.add(snapshot)
        db.session.commit()
        return project.id, snapshot.id


def test_create_run_executes_inventory_and_finishes(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "alice", "alice@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    response = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "先清点项目文件并告诉我项目结构", "mode": "baseline"},
        headers=auth_headers(agent_api_app, user_id),
    )
    assert response.status_code == 201
    run = response.json["run"]
    assert run["status"] == "completed"
    assert run["snapshot_id"] == snapshot_id
    assert run["tool_call_count"] == 5

    detail = client.get(f"/api/security/agent-runs/{run['id']}", headers=auth_headers(agent_api_app, user_id))
    assert detail.status_code == 200
    payload = detail.json
    assert payload["run"]["id"] == run["id"]
    assert payload["plan"]["planner_source"] == "rule_based_policy"
    assert [node["node_key"] for node in payload["plan"]["nodes"]] == [
        "inventory",
        "baseline_scan",
        "coverage_analysis",
        "risk_ranking",
        "report",
    ]
    assert len(payload["steps"]) == 5
    assert len(payload["tool_calls"]) == 5
    assert payload["tool_calls"][0]["tool_name"] == "inventory_snapshot"
    assert "文件" in payload["tool_calls"][0]["output_summary"]
    assert payload["last_sequence"] >= 10
    assert payload["messages"][0]["role"] == "user"

    events = client.get(
        f"/api/security/agent-runs/{run['id']}/events", headers=auth_headers(agent_api_app, user_id)
    )
    assert events.status_code == 200
    event_types = [item["event_type"] for item in events.json["items"]]
    for expected in ("run.created", "plan.created", "step.started", "tool.started", "tool.completed", "step.completed", "run.completed"):
        assert expected in event_types


def test_create_run_validation(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "alice2", "alice2@example.test")
    project_id, _ = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    empty = client.post(f"/api/security/projects/{project_id}/agent-runs", json={}, headers=headers)
    assert empty.status_code == 400

    bad_mode = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "g", "mode": "quantum"},
        headers=headers,
    )
    assert bad_mode.status_code == 400


def test_create_run_without_snapshot_conflicts(agent_api_app):
    user_id, workspace_id = make_user(agent_api_app, "alice3", "alice3@example.test")
    client = agent_api_app.test_client()
    with agent_api_app.app_context():
        project = SecurityProject(workspace_id=workspace_id, name="empty", created_by=user_id)
        db.session.add(project)
        db.session.commit()
        project_id = project.id
    response = client.post(
        f"/api/security/projects/{project_id}/agent-runs",
        json={"goal_text": "清点"},
        headers=auth_headers(agent_api_app, user_id),
    )
    assert response.status_code == 409


def test_pause_resume_cancel_flow(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "dave", "dave@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    with agent_api_app.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            created_by=user_id,
            goal_text="g",
            mode="baseline",
            status=AgentRunStatus.EXECUTING_TOOLS.value,
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    paused = client.post(f"/api/security/agent-runs/{run_id}/pause", headers=headers)
    assert paused.status_code == 200
    assert paused.json["run"]["status"] == "paused"

    resumed = client.post(f"/api/security/agent-runs/{run_id}/resume", headers=headers)
    assert resumed.status_code == 200
    assert resumed.json["run"]["status"] == "completed"

    canceled = client.post(f"/api/security/agent-runs/{run_id}/cancel", headers=headers)
    assert canceled.status_code == 409


def test_cancel_stops_remaining_nodes_and_no_new_tool_calls(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "erin", "erin@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    with agent_api_app.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            created_by=user_id,
            goal_text="g",
            mode="baseline",
            status=AgentRunStatus.EXECUTING_TOOLS.value,
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    canceled = client.post(f"/api/security/agent-runs/{run_id}/cancel", headers=headers)
    assert canceled.status_code == 200
    assert canceled.json["run"]["status"] == "canceled"

    detail = client.get(f"/api/security/agent-runs/{run_id}", headers=headers)
    assert detail.json["tool_calls"] == []
    assert detail.json["steps"] == []
