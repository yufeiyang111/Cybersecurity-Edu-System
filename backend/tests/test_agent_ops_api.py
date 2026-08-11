# -*- coding: utf-8 -*-
"""A8-A9 API 测试：provider 策略端点与可观测性端点。"""
from __future__ import annotations

from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_llm import LLMInvocation
from app.models.agent_runtime import AgentRun, AgentRunMode, AgentRunStatus
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User


def _make_user(application, username="hana", role="owner"):
    with application.app_context():
        user = User(username=username, email=f"{username}@t", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name=f"ws-{username}", slug=f"ws-{username}")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
        )
        db.session.commit()
        return user.id, workspace.id


def _auth_headers(application, user_id):
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _make_run(application, user_id, workspace_id, tmp_path):
    with application.app_context():
        project = SecurityProject(workspace_id=workspace_id, name="p", created_by=user_id)
        db.session.add(project)
        db.session.flush()
        root = tmp_path / "snap"
        root.mkdir(parents=True, exist_ok=True)
        (root / "app.py").write_text("import os\n", encoding="utf-8")
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="abc",
            storage_path=str(root),
            file_count=1,
            total_bytes=10,
        )
        db.session.add(snapshot)
        db.session.flush()
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project.id,
            snapshot_id=snapshot.id,
            created_by=user_id,
            goal_text="检查风险",
            mode=AgentRunMode.BASELINE.value,
            status=AgentRunStatus.COMPLETED.value,
        )
        db.session.add(run)
        db.session.flush()
        db.session.add(
            LLMInvocation(
                run_id=run.id,
                workspace_id=workspace_id,
                user_id=user_id,
                provider_name="minimax",
                model="m",
                operation="planner",
                status="success",
                total_tokens=20,
                total_cost=0.002,
                usage_source="provider_reported",
            )
        )
        db.session.commit()
        return run.id


def test_provider_policy_get_update(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()
    response = client.get(
        f"/api/security/workspaces/{workspace_id}/agent-provider-policy", headers=headers
    )
    assert response.status_code == 200
    assert response.get_json()["policy"]["allowlist"] == []
    updated = client.put(
        f"/api/security/workspaces/{workspace_id}/agent-provider-policy",
        headers=headers,
        json={"allowlist": ["minimax", "dashscope"], "preferred_provider": "minimax"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["policy"]["preferred_provider"] == "minimax"


def test_provider_policy_rejects_unknown_provider(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().put(
        f"/api/security/workspaces/{workspace_id}/agent-provider-policy",
        headers=headers,
        json={"allowlist": ["bogus"]},
    )
    assert response.status_code == 400


def test_provider_policy_cross_workspace_forbidden(agent_api_app, tmp_path):
    owner_id, workspace_id = _make_user(agent_api_app, username="hana")
    outsider_id, _ = _make_user(agent_api_app, username="ivan")
    headers = _auth_headers(agent_api_app, outsider_id)
    response = agent_api_app.test_client().get(
        f"/api/security/workspaces/{workspace_id}/agent-provider-policy", headers=headers
    )
    assert response.status_code == 403


def test_observability_overview_api(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    _make_run(agent_api_app, user_id, workspace_id, tmp_path)
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent/observability/overview?workspace_id={workspace_id}&days=7",
        headers=headers,
    )
    assert response.status_code == 200
    overview = response.get_json()["overview"]
    assert overview["run_counts"]["total"] >= 1
    assert overview["llm"]["total_tokens"] == 20
    assert overview["llm"]["providers"][0]["provider_name"] == "minimax"


def test_observability_runs_api(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id = _make_run(agent_api_app, user_id, workspace_id, tmp_path)
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent/observability/runs?workspace_id={workspace_id}&status=completed",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] >= 1
    assert data["items"][0]["id"] == run_id
    assert data["items"][0]["approval_pending"] is False


def test_observability_cross_workspace_forbidden(agent_api_app, tmp_path):
    owner_id, workspace_id = _make_user(agent_api_app, username="hana")
    outsider_id, _ = _make_user(agent_api_app, username="ivan")
    headers = _auth_headers(agent_api_app, outsider_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent/observability/overview?workspace_id={workspace_id}",
        headers=headers,
    )
    assert response.status_code == 403
