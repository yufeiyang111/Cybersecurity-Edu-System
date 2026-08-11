# -*- coding: utf-8 -*-
"""A7 approvals + observation review API 测试。"""
from __future__ import annotations

from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_approval import AgentApproval, ApprovalStatus
from app.models.agent_review import AgentObservation, ObservationStatus
from app.models.agent_runtime import AgentRun, AgentRunMode, AgentRunStatus
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.security_agent.approval_service import ApprovalService as ApprovalSvc


def _make_user(application, username="erin", role="owner"):
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


def _make_run(application, user_id, workspace_id, tmp_path, *, status=AgentRunStatus.AWAITING_APPROVAL.value):
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
            goal_text="检查项目风险",
            mode=AgentRunMode.BASELINE.value,
            status=status,
        )
        db.session.add(run)
        db.session.commit()
        return run.id


def _request_approval(application, run_id, **kwargs):
    """在 app context 内重新加载 run 并创建审批，避免 detached 实例。"""
    from app import db
    from app.models.agent_runtime import AgentRun

    with application.app_context():
        run = db.session.get(AgentRun, run_id)
        approval = ApprovalSvc().request(run, **kwargs)
        return approval.id


def test_approval_queue_and_resolve(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id = _make_run(agent_api_app, user_id, workspace_id, tmp_path)
    approval_id = _request_approval(
        agent_api_app, run_id, operation_type="budget_increase", reason="预算超限，等待批准"
    )
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()

    queue = client.get(
        f"/api/security/agent-approvals?workspace_id={workspace_id}&page=1&page_size=10",
        headers=headers,
    )
    assert queue.status_code == 200
    data = queue.get_json()
    assert data["total"] == 1
    assert data["items"][0]["operation_type"] == "budget_increase"
    assert data["items"][0]["can_resolve"] is True
    assert data["items"][0]["run_goal"] == "检查项目风险"

    resolved = client.post(
        f"/api/security/agent-runs/{run_id}/approvals/{approval_id}/resolve",
        headers=headers,
        json={"decision": "approved", "comment": "同意追加预算"},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["approval"]["status"] == "approved"


def test_analyst_cannot_resolve_medium_approval(agent_api_app, tmp_path):
    owner_id, workspace_id = _make_user(agent_api_app, username="erin")
    run_id = _make_run(agent_api_app, owner_id, workspace_id, tmp_path)
    analyst_id, _ = _make_user(agent_api_app, username="frank", role="analyst")
    approval_id = _request_approval(agent_api_app, run_id, operation_type="budget_increase", reason="r")
    headers = _auth_headers(agent_api_app, analyst_id)
    response = agent_api_app.test_client().post(
        f"/api/security/agent-runs/{run_id}/approvals/{approval_id}/resolve",
        headers=headers,
        json={"decision": "approved", "comment": ""},
    )
    assert response.status_code == 403


def test_approval_resolve_twice_conflicts(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id = _make_run(agent_api_app, user_id, workspace_id, tmp_path)
    approval_id = _request_approval(agent_api_app, run_id, operation_type="budget_increase", reason="r")
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()
    first = client.post(
        f"/api/security/agent-runs/{run_id}/approvals/{approval_id}/resolve",
        headers=headers,
        json={"decision": "rejected", "comment": "不批"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/security/agent-runs/{run_id}/approvals/{approval_id}/resolve",
        headers=headers,
        json={"decision": "approved", "comment": ""},
    )
    assert second.status_code == 409


def test_approval_queue_cross_workspace_forbidden(agent_api_app, tmp_path):
    owner_id, workspace_id = _make_user(agent_api_app, username="erin")
    _make_run(agent_api_app, owner_id, workspace_id, tmp_path)
    outsider_id, _ = _make_user(agent_api_app, username="grace")
    headers = _auth_headers(agent_api_app, outsider_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent-approvals?workspace_id={workspace_id}",
        headers=headers,
    )
    assert response.status_code == 403


def test_observation_review_api(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id = _make_run(agent_api_app, user_id, workspace_id, tmp_path, status=AgentRunStatus.COMPLETED.value)
    with agent_api_app.app_context():
        observation = AgentObservation(
            run_id=run_id,
            title="XSS",
            status=ObservationStatus.UNVERIFIED.value,
            confidence="medium",
            summary="输入未转义",
        )
        db.session.add(observation)
        db.session.commit()
        observation_id = observation.id
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()
    response = client.post(
        f"/api/security/agent-runs/{run_id}/observations/{observation_id}/review",
        headers=headers,
        json={"decision": "confirmed", "comment": "证据充分，确认"},
    )
    assert response.status_code == 200
    assert response.get_json()["observation"]["status"] == "confirmed"
    second = client.post(
        f"/api/security/agent-runs/{run_id}/observations/{observation_id}/review",
        headers=headers,
        json={"decision": "rejected", "comment": ""},
    )
    assert second.status_code == 409


def test_run_approvals_list(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    run_id = _make_run(agent_api_app, user_id, workspace_id, tmp_path)
    _request_approval(agent_api_app, run_id, operation_type="budget_increase", reason="r")
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/approvals", headers=headers
    )
    assert response.status_code == 200
    assert len(response.get_json()["items"]) == 1
