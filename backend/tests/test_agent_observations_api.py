# -*- coding: utf-8 -*-
"""A6 observations API 测试：列表分页、详情、跨 workspace 拒绝。"""
from __future__ import annotations

from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_review import AgentObservation
from app.models.agent_runtime import AgentRun, AgentRunMode, AgentRunStatus
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.security_agent.observation_service import ObservationService


def _make_user(application, username="carol"):
    with application.app_context():
        user = User(username=username, email=f"{username}@t", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name=f"ws-{username}", slug=f"ws-{username}")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        )
        db.session.commit()
        return user.id, workspace.id


def _auth_headers(application, user_id):
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _make_run_with_observation(application, user_id, workspace_id, tmp_path, *, status=AgentRunStatus.COMPLETED.value):
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
            goal_text="g",
            mode=AgentRunMode.BASELINE.value,
            status=status,
        )
        db.session.add(run)
        db.session.flush()
        observation = ObservationService().create(
            run,
            {
                "title": "观察结论 A",
                "summary": "摘要内容",
                "confidence": "medium",
                "locations": [{"file_path": "app.py", "start_line": 1, "role": "sink"}],
                "citations": [
                    {
                        "source_type": "rag",
                        "document_id": "d1",
                        "document_title": "规范文档",
                        "trust_score": 0.9,
                        "content_digest": "digest-1",
                    }
                ],
                "proof_gaps": ["gap"],
            },
        )
        db.session.commit()
        return run.id, observation.id


def test_list_observations_paged(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id, _ = _make_run_with_observation(agent_api_app, user_id, workspace_id, tmp_path)
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()
    response = client.get(
        f"/api/security/agent-runs/{run_id}/observations?page=1&page_size=10",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "观察结论 A"
    assert data["items"][0]["status"] == "unverified"
    assert data["items"][0]["confidence"] == "medium"


def test_get_observation_detail(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id, observation_id = _make_run_with_observation(agent_api_app, user_id, workspace_id, tmp_path)
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/observations/{observation_id}",
        headers=headers,
    )
    assert response.status_code == 200
    observation = response.get_json()["observation"]
    assert observation["locations"][0]["file_path"] == "app.py"
    assert observation["citations"][0]["document_title"] == "规范文档"
    assert observation["citations"][0]["trust_score"] == 0.9
    assert "detail" in observation


def test_get_observation_not_found(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id, _ = _make_run_with_observation(agent_api_app, user_id, workspace_id, tmp_path)
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/observations/99999",
        headers=headers,
    )
    assert response.status_code == 404


def test_observations_cross_workspace_forbidden(agent_api_app, tmp_path):
    owner_id, owner_ws = _make_user(agent_api_app, username="carol")
    run_id, _ = _make_run_with_observation(agent_api_app, owner_id, owner_ws, tmp_path)
    outsider_id, _ = _make_user(agent_api_app, username="dave")
    headers = _auth_headers(agent_api_app, outsider_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/observations",
        headers=headers,
    )
    assert response.status_code == 403


def test_list_observations_validates_pagination(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id, _ = _make_run_with_observation(agent_api_app, user_id, workspace_id, tmp_path)
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/observations?page=0",
        headers=headers,
    )
    assert response.status_code == 400
