"""Tests for the rescan endpoint and snapshot reuse behavior."""
import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.security import ProjectSnapshot, ScanTask, SecurityProject
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
        "RescanTestConfig",
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


def rescan_project(client, headers, project_id):
    return client.post(f"/api/security/projects/{project_id}/rescan", headers=headers)


def test_rescan_reuses_existing_zip_snapshot(api_app, tmp_path):
    user_id = make_user(api_app, "rescan", "rescan@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project = client.post("/api/security/projects", json={"name": "p1"}, headers=headers).json["project"]

    archive_path = make_zip(
        tmp_path,
        {"app.py": "import os\nos.system('echo hi')\n"},
    )
    first = upload_project(client, headers, project["id"], archive_path)
    snapshot_id = first["snapshot"]["id"]

    response = rescan_project(client, headers, project["id"])
    assert response.status_code == 202
    payload = response.json

    with api_app.app_context():
        snapshot = db.session.get(ProjectSnapshot, snapshot_id)
        assert snapshot is not None
        task_count = ScanTask.query.filter_by(snapshot_id=snapshot_id).count()
    assert task_count == 2
    assert payload["snapshot"]["id"] == snapshot_id
    assert payload["task"]["status"] == "completed"


def test_rescan_requires_existing_snapshot(api_app, tmp_path):
    user_id = make_user(api_app, "empty", "empty@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project = client.post("/api/security/projects", json={"name": "no-snap"}, headers=headers).json["project"]

    response = rescan_project(client, headers, project["id"])
    assert response.status_code == 502


def test_rescan_rejects_non_member(api_app, tmp_path):
    owner = make_user(api_app, "owner", "owner@example.test")
    intruder = make_user(api_app, "intruder", "intruder@example.test")
    with api_app.app_context():
        from app.models.security import Workspace, WorkspaceMember

        workspace = Workspace(name="Private", slug="private-rescan")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner, role="owner"))
        project = SecurityProject(workspace_id=workspace.id, name="private", created_by=owner)
        db.session.add(project)
        db.session.flush()
        archive_root = tmp_path / "snapshot"
        archive_root.mkdir()
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="a" * 64,
            storage_path=str(archive_root),
            file_count=1,
            total_bytes=8,
        )
        db.session.add(snapshot)
        db.session.commit()
        project_id = project.id

    client = api_app.test_client()
    headers = auth_headers(api_app, intruder)
    response = rescan_project(client, headers, project_id)
    assert response.status_code == 403
