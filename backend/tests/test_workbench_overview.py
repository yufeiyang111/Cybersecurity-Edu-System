import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.security import ProjectSnapshot, ScanTask, SecurityFinding, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User


def install_route_stubs(monkeypatch):
    for module_name, blueprint_name in {
        "app.routes.auth": "auth_bp",
        "app.routes.knowledge": "knowledge_bp",
        "app.routes.qa": "qa_bp",
        "app.routes.admin": "admin_bp",
    }.items():
        module = types.ModuleType(module_name)
        setattr(module, blueprint_name, Blueprint(blueprint_name, module_name))
        monkeypatch.setitem(sys.modules, module_name, module)


@pytest.fixture
def api_app(tmp_path, monkeypatch):
    from conftest import TestConfig

    install_route_stubs(monkeypatch)
    config = type(
        "WorkbenchTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "RQ_ASYNC": False,
        },
    )
    application = create_app(config)
    with application.app_context():
        import app.models

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def make_user(application, username, email):
    with application.app_context():
        user = User(username=username, email=email, password_hash="x")
        db.session.add(user)
        db.session.commit()
        return user.id


def auth_headers(application, user_id):
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def make_zip(tmp_path, contents):
    archive_path = tmp_path / "project.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    return archive_path


def upload_project(client, headers, project_id, archive_path):
    with archive_path.open("rb") as archive:
        response = client.post(
            f"/api/security/projects/{project_id}/snapshots:upload",
            data={"archive": (archive, "project.zip")},
            content_type="multipart/form-data",
            headers=headers,
        )
    assert response.status_code == 202
    return response.json


def test_workbench_overview_aggregates_latest_task(api_app, tmp_path):
    user_id = make_user(api_app, "overview", "overview@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project = client.post("/api/security/projects", json={"name": "p1"}, headers=headers).json["project"]
    archive_path = make_zip(
        tmp_path,
        {
            "app.py": "import os\nos.system(user_input)\n",
            "config.js": "eval(payload);\n",
        },
    )
    upload_project(client, headers, project["id"], archive_path)

    overview = client.get("/api/security/workbench/overview", headers=headers)
    assert overview.status_code == 200
    payload = overview.json
    assert payload["total_projects"] == 1
    assert payload["total_scans"] == 1

    critical = payload["totals"]["critical"] + payload["totals"]["high"]
    assert critical >= 1

    assert len(payload["recent_scans"]) == 1
    assert payload["recent_scans"][0]["project_name"] == "p1"
    assert payload["recent_scans"][0]["status"] in {"completed", "completed_with_warnings"}
    assert payload["recent_scans"][0]["findings_count"] >= 1

    projects = client.get("/api/security/projects", headers=headers)
    assert projects.status_code == 200
    item = projects.json["items"][0]
    assert item["name"] == "p1"
    assert item["language"]
    assert item["latest_task_id"] is not None
    assert item["files"] == 2
    assert item["last_scan_at"] is not None
    assert item["vulns"]["total"] >= 1


def test_project_list_vulns_match_overview_totals(api_app, tmp_path):
    user_id = make_user(api_app, "match", "match@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_a = client.post("/api/security/projects", json={"name": "a"}, headers=headers).json["project"]
    project_b = client.post("/api/security/projects", json={"name": "b"}, headers=headers).json["project"]
    for project_id in (project_a["id"], project_b["id"]):
        archive_path = make_zip(
            tmp_path,
            {"danger.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n"},
        )
        upload_project(client, headers, project_id, archive_path)

    projects = client.get("/api/security/projects", headers=headers).json["items"]
    overview = client.get("/api/security/workbench/overview", headers=headers).json

    summed = {sev: 0 for sev in ("critical", "high", "medium", "low", "info")}
    for item in projects:
        for sev in summed:
            summed[sev] += item["vulns"].get(sev, 0)
    for sev in summed:
        assert overview["totals"][sev] == summed[sev]

    assert overview["total_projects"] == 2
    assert overview["total_scans"] == 2


def test_workbench_overview_is_workspace_scoped(api_app, tmp_path):
    alice = make_user(api_app, "scope-alice", "scope-alice@example.test")
    bob = make_user(api_app, "scope-bob", "scope-bob@example.test")
    with api_app.app_context():
        workspace = Workspace(name="Scope Private", slug="scope-private")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=bob, role="owner"))
        project = SecurityProject(workspace_id=workspace.id, name="private", created_by=bob)
        db.session.add(project)
        db.session.flush()
        archive_root = tmp_path / "scope-snapshot"
        archive_root.mkdir()
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="e" * 64,
            storage_path=str(archive_root),
            file_count=1,
            total_bytes=8,
        )
        db.session.add(snapshot)
        db.session.flush()
        task = ScanTask(
            snapshot_id=snapshot.id,
            status="completed",
            summary_json={"languages": ["python"], "findings_count": 1},
            dispatch_key="scope-secret-task",
        )
        db.session.add(task)
        db.session.flush()
        finding = SecurityFinding(
            task_id=task.id,
            fingerprint="scope-fp",
            rule_id="PY-SHELL-TRUE",
            category="sast",
            severity="critical",
            status="open",
            file_path="danger.py",
            start_line=1,
            message="command injection",
        )
        db.session.add(finding)
        db.session.commit()

    client = api_app.test_client()
    alice_headers = auth_headers(api_app, alice)
    alice_projects = client.get("/api/security/projects", headers=alice_headers).json["items"]
    alice_overview = client.get("/api/security/workbench/overview", headers=alice_headers).json
    assert alice_projects == []
    assert alice_overview["total_projects"] == 0
    assert alice_overview["total_scans"] == 0
    assert alice_overview["totals"]["critical"] == 0