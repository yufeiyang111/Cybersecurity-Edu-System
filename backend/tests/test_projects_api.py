from pathlib import Path
import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.security import AuditEvent, ProjectSnapshot, ScanTask, SecurityProject, SnapshotDependency, Workspace, WorkspaceMember
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


def test_user_cannot_import_github_snapshot_in_another_workspace(api_app):
    alice = make_user(api_app, "github-alice", "github-alice@example.test")
    bob = make_user(api_app, "github-bob", "github-bob@example.test")
    with api_app.app_context():
        workspace = Workspace(name="GitHub Bob", slug="github-bob-workspace")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=bob, role="owner"))
        project = SecurityProject(workspace_id=workspace.id, name="private-github", created_by=bob)
        db.session.add(project)
        db.session.commit()
        project_id = project.id

    response = api_app.test_client().post(
        f"/api/security/projects/{project_id}/snapshots:github",
        json={"repository_url": "https://github.com/octo/demo"},
        headers=auth_headers(api_app, alice),
    )

    assert response.status_code == 403
    assert response.json == {"error": "无权访问该工作区"}


def test_github_import_rejects_invalid_repository_url_at_api_boundary(api_app):
    user_id = make_user(api_app, "github-url", "github-url@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "github-url-demo"}, headers=headers).json["project"]["id"]

    response = client.post(
        f"/api/security/projects/{project_id}/snapshots:github",
        json={"repository_url": "https://example.com/octo/demo"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json == {"error": "GitHub 仓库地址无效"}


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


def test_github_import_uses_safe_archive_then_creates_snapshot(api_app, tmp_path, monkeypatch):
    from app.services.github_source import GitHubArchiveMetadata, GitHubRepositoryRef

    user_id = make_user(api_app, "alice", "alice@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "github-demo"}, headers=headers).json["project"]["id"]

    downloaded = tmp_path / "downloaded.zip"
    with zipfile.ZipFile(downloaded, "w") as archive:
        archive.writestr("repo-main/index.js", "eval(payload);\n")

    configured_redirect_limit: dict[str, int | None] = {}

    def fake_download(repository_url, destination, max_bytes, timeout_seconds, max_redirects=None):
        configured_redirect_limit["value"] = max_redirects
        Path(destination).write_bytes(downloaded.read_bytes())
        return GitHubArchiveMetadata(
            repository=GitHubRepositoryRef("octo", "demo", "https://github.com/octo/demo"),
            source_ref="https://github.com/octo/demo",
            default_branch="main",
            commit_sha="a" * 40,
            archive_path=Path(destination),
            archive_bytes=downloaded.stat().st_size,
        )

    monkeypatch.setattr("app.services.snapshot_service.download_public_github_archive", fake_download)
    response = client.post(
        f"/api/security/projects/{project_id}/snapshots:github",
        json={"repository_url": "https://github.com/octo/demo"},
        headers=headers,
    )

    assert response.status_code == 202
    assert configured_redirect_limit == {"value": 1}
    assert response.json["snapshot"]["source_type"] == "github"
    assert response.json["snapshot"]["commit_sha"] == "a" * 40
    assert response.json["task"]["status"] == "completed"
    findings = client.get(f"/api/security/tasks/{response.json['task']['id']}/findings", headers=headers)
    assert {item["rule_id"] for item in findings.json["items"]} == {"JS-EVAL"}



def test_github_import_accepts_one_github_wrapper_directory_above_project_depth(api_app, tmp_path, monkeypatch):
    from app.services.github_source import GitHubArchiveMetadata, GitHubRepositoryRef

    user_id = make_user(api_app, "github-depth", "github-depth@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "github-depth-demo"}, headers=headers).json["project"]["id"]
    archive_member = "repo-main/backend/src/main/java/com/labex/labexagent/tool/impl/AgentTool.js"
    downloaded = tmp_path / "github-depth.zip"
    with zipfile.ZipFile(downloaded, "w") as archive:
        archive.writestr(archive_member, "eval(payload);\n")

    def fake_download(repository_url, destination, max_bytes, timeout_seconds, max_redirects=None):
        del repository_url, max_bytes, timeout_seconds, max_redirects
        Path(destination).write_bytes(downloaded.read_bytes())
        return GitHubArchiveMetadata(
            repository=GitHubRepositoryRef("octo", "demo", "https://github.com/octo/demo"),
            source_ref="https://github.com/octo/demo",
            default_branch="main",
            commit_sha="b" * 40,
            archive_path=Path(destination),
            archive_bytes=downloaded.stat().st_size,
        )

    monkeypatch.setattr("app.services.snapshot_service.download_public_github_archive", fake_download)
    response = client.post(
        f"/api/security/projects/{project_id}/snapshots:github",
        json={"repository_url": "https://github.com/octo/demo"},
        headers=headers,
    )

    assert response.status_code == 202
    findings = client.get(f"/api/security/tasks/{response.json['task']['id']}/findings", headers=headers)
    assert {item["rule_id"] for item in findings.json["items"]} == {"JS-EVAL"}


def test_zip_upload_keeps_project_path_depth_limit(api_app, tmp_path):
    user_id = make_user(api_app, "zip-depth", "zip-depth@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "zip-depth-demo"}, headers=headers).json["project"]["id"]
    archive_path = make_zip(
        tmp_path,
        {"repo-main/backend/src/main/java/com/labex/labexagent/tool/impl/AgentTool.js": "eval(payload);\n"},
    )

    with archive_path.open("rb") as archive:
        response = client.post(
            f"/api/security/projects/{project_id}/snapshots:upload",
            data={"archive": (archive, "deep-project.zip")},
            content_type="multipart/form-data",
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json["error"] == "压缩包路径层级超过安全限制"


def test_project_dependencies_are_workspace_scoped(api_app, tmp_path):
    user_id = make_user(api_app, "alice", "alice@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "dependency-demo"}, headers=headers).json["project"]["id"]
    archive_path = make_zip(tmp_path, {"requirements.txt": "requests==2.31.0\n"})

    with archive_path.open("rb") as archive:
        response = client.post(
            f"/api/security/projects/{project_id}/snapshots:upload",
            data={"archive": (archive, "demo.zip")},
            content_type="multipart/form-data",
            headers=headers,
        )

    assert response.status_code == 202
    dependencies = client.get(f"/api/security/projects/{project_id}/dependencies", headers=headers)
    assert dependencies.status_code == 200
    assert [(item["ecosystem"], item["package_name"]) for item in dependencies.json["items"]] == [("PyPI", "requests")]


def test_security_routes_are_backed_by_domain_modules():
    required_modules = (
        "app.routes.security.common",
        "app.routes.security.projects",
        "app.routes.security.snapshots",
        "app.routes.security.tasks",
        "app.routes.security.knowledge",
        "app.routes.security.remediation",
    )

    for module_name in required_modules:
        assert __import__("importlib").util.find_spec(module_name) is not None

    from app.routes.projects import projects_bp

    assert projects_bp.name == "projects"


def test_task_cancel_and_retry_are_authorized_and_recoverable(api_app, tmp_path):
    user_id = make_user(api_app, "task-control", "task-control@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project_id = client.post("/api/security/projects", json={"name": "task-control"}, headers=headers).json["project"]["id"]
    snapshot_root = tmp_path / "task-control-snapshot"
    snapshot_root.mkdir()
    (snapshot_root / "safe.py").write_text("print(\"ok\")\\n", encoding="utf-8")
    with api_app.app_context():
        snapshot = ProjectSnapshot(
            project_id=project_id,
            source_type="zip",
            content_sha256="c" * 64,
            storage_path=str(snapshot_root),
            file_count=1,
            total_bytes=12,
        )
        db.session.add(snapshot)
        db.session.flush()
        task = ScanTask(snapshot_id=snapshot.id, status="created", dispatch_key="api-control")
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    canceled = client.post(f"/api/security/tasks/{task_id}/cancel", headers=headers)
    assert canceled.status_code == 200
    assert canceled.json["task"]["status"] == "canceled"

    retried = client.post(f"/api/security/tasks/{task_id}/retry", headers=headers)
    assert retried.status_code == 202
    assert retried.json["task"]["retry_count"] == 1
    assert retried.json["task"]["status"] in {"completed", "completed_with_warnings", "failed"}

    with api_app.app_context():
        audit_actions = {event.action for event in AuditEvent.query.all()}
        assert {"scan.canceled", "scan.retry_requested"}.issubset(audit_actions)


def test_task_controls_are_workspace_scoped(api_app, tmp_path):
    alice = make_user(api_app, "task-alice", "task-alice@example.test")
    bob = make_user(api_app, "task-bob", "task-bob@example.test")
    with api_app.app_context():
        workspace = Workspace(name="Task Private", slug="task-private")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=bob, role="owner"))
        project = SecurityProject(workspace_id=workspace.id, name="private-task", created_by=bob)
        db.session.add(project)
        db.session.flush()
        snapshot_root = tmp_path / "private-task-snapshot"
        snapshot_root.mkdir()
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="d" * 64,
            storage_path=str(snapshot_root),
            file_count=0,
            total_bytes=0,
        )
        db.session.add(snapshot)
        db.session.flush()
        task = ScanTask(snapshot_id=snapshot.id, status="created", dispatch_key="private-task")
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    client = api_app.test_client()
    alice_headers = auth_headers(api_app, alice)
    assert client.post(f"/api/security/tasks/{task_id}/cancel", headers=alice_headers).status_code == 403
    assert client.post(f"/api/security/tasks/{task_id}/retry", headers=alice_headers).status_code == 403

def test_findings_api_includes_explainable_risk_and_risk_sorting(api_app, tmp_path):
    user_id = make_user(api_app, "risk-user", "risk-user@example.test")
    client = api_app.test_client()
    headers = auth_headers(api_app, user_id)
    project = client.post("/api/security/projects", json={"name": "risk-project"}, headers=headers).json["project"]
    archive_path = make_zip(
        tmp_path,
        {"danger.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n"},
    )
    with archive_path.open("rb") as archive:
        uploaded = client.post(
            f"/api/security/projects/{project['id']}/snapshots:upload",
            data={"archive": (archive, "risk.zip")},
            content_type="multipart/form-data",
            headers=headers,
        )
    task_id = uploaded.json["task"]["id"]

    response = client.get(f"/api/security/tasks/{task_id}/findings?sort=risk", headers=headers)

    assert response.status_code == 200
    finding = response.json["items"][0]
    assert finding["risk"]["score"] >= 0
    assert finding["risk"]["priority"] in {"critical", "high", "medium", "low"}
    assert len(finding["risk"]["factors"]) == 10
    assert finding["risk"]["policy_version"] == "risk-v1"
