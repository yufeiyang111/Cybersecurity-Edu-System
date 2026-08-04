"""Coverage API tests: agent run coverage endpoint and authorization."""
from __future__ import annotations

from app import db
from app.models.security import ProjectSnapshot, ScanTask, SecurityProject
from app.models.user import User
from app.services.scan_coverage.catalog import catalog_snapshot_files
from app.services.scan_coverage.receipts import write_coverage_receipts_for_task
from app.services.workspaces import get_or_create_personal_workspace

from test_agent_run_api import (
    auth_headers,
    make_project_and_snapshot,
    make_user,
)


def _seed_task_with_receipts(agent_api_app, tmp_path, user_id, workspace_id, project_id, snapshot_id):
    with agent_api_app.app_context():
        snapshot = db.session.get(ProjectSnapshot, snapshot_id)
        catalog_snapshot_files(snapshot)
        task = ScanTask(snapshot_id=snapshot_id, status="completed")
        db.session.add(task)
        db.session.flush()
        root = tmp_path / "snapshot"
        write_coverage_receipts_for_task(task, root)
        db.session.commit()
        return task.id


def test_coverage_endpoint_returns_summary_and_files(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "coverage", "coverage@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    task_id = _seed_task_with_receipts(agent_api_app, tmp_path, user_id, workspace_id, project_id, snapshot_id)
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    with agent_api_app.app_context():
        run = __import__("app.models.agent_runtime", fromlist=["AgentRun"]).AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            created_by=user_id,
            goal_text="g",
            mode="baseline",
            status="completed",
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    response = client.get(f"/api/security/agent-runs/{run_id}/coverage", headers=headers)
    assert response.status_code == 200
    body = response.json
    assert body["coverage"]["total_files"] == 2
    assert body["coverage"]["specialized_sast"] == 2
    assert body["coverage"]["generic_only"] == 0
    assert len(body["files"]) == 2
    assert body["pagination"]["total"] == 2

    filtered = client.get(
        f"/api/security/agent-runs/{run_id}/coverage?kind=specialized_sast", headers=headers
    )
    assert filtered.status_code == 200
    assert len(filtered.json["files"]) == 2


def test_coverage_endpoint_denies_outsider(agent_api_app, tmp_path):
    user_id, workspace_id = make_user(agent_api_app, "cov2", "cov2@example.test")
    project_id, snapshot_id = make_project_and_snapshot(agent_api_app, tmp_path, user_id, workspace_id)
    task_id = _seed_task_with_receipts(agent_api_app, tmp_path, user_id, workspace_id, project_id, snapshot_id)
    outsider_id = make_user(agent_api_app, "cov3", "cov3@example.test")[0]
    client = agent_api_app.test_client()

    with agent_api_app.app_context():
        run = __import__("app.models.agent_runtime", fromlist=["AgentRun"]).AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            created_by=user_id,
            goal_text="g",
            mode="baseline",
            status="completed",
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    response = client.get(
        f"/api/security/agent-runs/{run_id}/coverage", headers=auth_headers(agent_api_app, outsider_id)
    )
    assert response.status_code == 403
