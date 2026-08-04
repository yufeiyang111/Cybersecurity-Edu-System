"""Project-level scan exclusion rules: API, authorization, audit, rescan flow."""
import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.security import AuditEvent, ProjectExclusionRule, ScanTask, SecurityProject
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
        "ExclusionTestConfig",
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


def create_project(client, headers):
    response = client.post("/api/security/projects", json={"name": "excl"}, headers=headers)
    assert response.status_code == 201
    return response.json["project"]["id"]


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


def add_rule(client, headers, project_id, pattern):
    return client.post(
        f"/api/security/projects/{project_id}/exclusions/items",
        json={"pattern": pattern},
        headers=headers,
    )


def test_rule_crud_and_order(api_app):
    user_id = make_user(api_app, "rule", "rule@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = create_project(client, headers)

    response = add_rule(client, headers, project_id, "*.xlsx")
    assert response.status_code == 201
    first_id = response.json["item"]["id"]
    response = add_rule(client, headers, project_id, "!重要说明.md")
    assert response.status_code == 201
    second_id = response.json["item"]["id"]

    listing = client.get(f"/api/security/projects/{project_id}/exclusions", headers=headers)
    assert listing.status_code == 200
    patterns = [item["pattern"] for item in listing.json["items"]]
    assert patterns == ["*.xlsx", "!重要说明.md"]

    response = client.delete(
        f"/api/security/projects/{project_id}/exclusions/items/{first_id}",
        headers=headers,
    )
    assert response.status_code == 204
    listing = client.get(f"/api/security/projects/{project_id}/exclusions", headers=headers)
    assert [item["id"] for item in listing.json["items"]] == [second_id]


def test_replace_exclusions_acts_like_gitignore_file(api_app):
    user_id = make_user(api_app, "replace", "replace@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = create_project(client, headers)

    add_rule(client, headers, project_id, "*.old")

    response = client.put(
        f"/api/security/projects/{project_id}/exclusions",
        json={"patterns": ["# comment", "docs/", "*.pem"]},
        headers=headers,
    )
    assert response.status_code == 200
    patterns = [item["pattern"] for item in response.json["items"]]
    assert patterns == ["docs/", "*.pem"]

    response = client.put(
        f"/api/security/projects/{project_id}/exclusions",
        json={"patterns": []},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json["items"] == []


def test_rule_validation_and_permissions(api_app):
    owner = make_user(api_app, "own", "own@example.test")
    intruder = make_user(api_app, "intruder", "intruder@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, owner)
    project_id = create_project(client, headers)

    invalid = add_rule(client, headers, project_id, "   # 注释")
    assert invalid.status_code == 400

    intruder_headers = auth_headers(api_app, intruder)
    forbidden = add_rule(client, intruder_headers, project_id, "*.xlsx")
    assert forbidden.status_code == 403
    read = client.get(f"/api/security/projects/{project_id}/exclusions", headers=intruder_headers)
    assert read.status_code == 403

    missing = client.get("/api/security/projects/999999/exclusions", headers=headers)
    assert missing.status_code == 404


def test_exclusions_are_audited(api_app):
    user_id = make_user(api_app, "audit", "audit@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = create_project(client, headers)

    add_rule(client, headers, project_id, "*.xlsx")

    with api_app.app_context():
        actions = [event.action for event in AuditEvent.query.order_by(AuditEvent.id.asc()).all()]
        assert "scan.exclusion.added" in actions


def test_rescan_respects_exclusion_rules(api_app, tmp_path):
    user_id = make_user(api_app, "flow", "flow@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = create_project(client, headers)

    archive_path = make_zip(
        tmp_path,
        {
            "app.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n",
            "secret.txt": "api_key = 'abcdef1234567890'\n",
        },
    )
    first = upload_project(client, headers, project_id, archive_path)
    snapshot_id = first["snapshot"]["id"]

    add_rule(client, headers, project_id, "secret.txt")
    response = client.post(f"/api/security/projects/{project_id}/rescan", headers=headers)
    assert response.status_code == 202
    assert response.json["snapshot"]["id"] == snapshot_id

    with api_app.app_context():
        tasks = (
            ScanTask.query.filter_by(snapshot_id=snapshot_id)
            .order_by(ScanTask.id.asc())
            .all()
        )
        latest = tasks[-1]
        assert latest.exclusion_rules == ["secret.txt"]
        assert latest.status in {"completed", "completed_with_warnings"}
        findings = [
            finding
            for finding in latest.findings
            if finding.file_path in {"secret.txt", "app.py"}
        ]
        assert {finding.file_path for finding in findings} == {"app.py"}


def test_new_upload_applies_exclusion_at_extract_time(api_app, tmp_path):
    user_id = make_user(api_app, "fresh", "fresh@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = create_project(client, headers)

    add_rule(client, headers, project_id, "docs/")

    archive_path = make_zip(
        tmp_path,
        {"app.py": "print('ok')\n", "docs/内部说明.txt": "api_key = 'secretvalue123'\n"},
    )
    result = upload_project(client, headers, project_id, archive_path)

    with api_app.app_context():
        from app.models.security import ProjectSnapshot

        snapshot = db.session.get(ProjectSnapshot, result["snapshot"]["id"])
        assert snapshot.file_count == 1
        tasks = ScanTask.query.filter_by(snapshot_id=snapshot.id).all()
        assert tasks
        task = tasks[-1]
        assert task.exclusion_rules == ["docs/"]
        assert all(finding.file_path != "docs/内部说明.txt" for finding in task.findings)
