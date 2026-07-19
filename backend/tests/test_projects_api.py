from pathlib import Path
import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.security import AuditEvent, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User


def install_legacy_route_stubs(monkeypatch):
    import app.routes
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
    install_legacy_route_stubs(monkeypatch)
    config = type("ApiTestConfig", (TestConfig,), {
        "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "LOG_FILE": str(tmp_path / "logs" / "test.log"),
        "RQ_ASYNC": False,
    })
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


def test_upload_creates_snapshot_and_completed_inline_task(api_app, tmp_path):
    user_id = make_user(api_app, "alice", "alice@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project = client.post("/api/security/projects", json={"name": "demo"}, headers=headers).json["project"]
    archive_path = make_zip(tmp_path, {"danger.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n"})

    with archive_path.open("rb") as archive:
        response = client.post(
            f"/api/security/projects/{project['id']}/snapshots:upload",
            data={"archive": (archive, "demo.zip")},
            content_type="multipart/form-data",
            headers=headers,
        )

    assert response.status_code == 202
    assert response.json["task"]["status"] == "completed"
    with api_app.app_context():
        audit = AuditEvent.query.filter_by(action="scan.uploaded").one()
        assert audit.target_id == response.json["task"]["id"]
        assert audit.metadata_json["file_count"] == 1
    findings = client.get(f"/api/security/tasks/{response.json['task']['id']}/findings", headers=headers)
    assert findings.status_code == 200
    assert findings.json["items"][0]["rule_id"] == "PY-SHELL-TRUE"


def test_user_cannot_upload_to_project_in_another_workspace(api_app, tmp_path):
    alice = make_user(api_app, "alice", "alice@example.test")
    bob = make_user(api_app, "bob", "bob@example.test")
    with api_app.app_context():
        workspace = Workspace(name="Bob", slug="bob-workspace")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=bob, role="owner"))
        project = SecurityProject(workspace_id=workspace.id, name="private", created_by=bob)
        db.session.add(project)
        db.session.commit()
        project_id = project.id
    archive_path = make_zip(tmp_path, {"app.py": "print('safe')"})

    with archive_path.open("rb") as archive:
        response = api_app.test_client().post(
            f"/api/security/projects/{project_id}/snapshots:upload",
            data={"archive": (archive, "demo.zip")},
            content_type="multipart/form-data",
            headers=auth_headers(api_app, alice),
        )

    assert response.status_code == 403
    assert response.json == {"error": "无权访问该工作区"}


def test_upload_rejects_missing_non_zip_and_traversal_archives(api_app, tmp_path):
    user_id = make_user(api_app, "alice", "alice@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "demo"}, headers=headers).json["project"]["id"]

    assert client.post(f"/api/security/projects/{project_id}/snapshots:upload", headers=headers).status_code == 400
    response = client.post(
        f"/api/security/projects/{project_id}/snapshots:upload",
        data={"archive": (Path(__file__).open("rb"), "not-a-zip.txt")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert response.status_code == 400

    archive_path = make_zip(tmp_path, {"../escaped.py": "print('unsafe')"})
    with archive_path.open("rb") as archive:
        response = client.post(
            f"/api/security/projects/{project_id}/snapshots:upload",
            data={"archive": (archive, "malicious.zip")},
            content_type="multipart/form-data",
            headers=headers,
        )
    assert response.status_code == 400
