from __future__ import annotations

import io
import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.security import (
    AuditEvent,
    ProjectSnapshot,
    ScanTask,
    SecurityFinding,
    SecurityProject,
    SecurityKnowledgeSource,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User


def _install_legacy_route_stubs(monkeypatch):
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

    _install_legacy_route_stubs(monkeypatch)
    config = type(
        "RemediationApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "RQ_ASYNC": False,
            "REMEDIATION_LLM_ENABLED": False,
            "REMEDIATION_MAX_CONTEXT_CHARS": 2_000,
            "REMEDIATION_MAX_OUTPUT_CHARS": 4_000,
            "REMEDIATION_RETRIEVAL_TOP_K": 3,
            "REMEDIATION_PATCH_MAX_LINES": 100,
            "REMEDIATION_PATCH_MAX_CHARS": 10_000,
        },
    )
    application = create_app(config)
    with application.app_context():
        import app.models  # noqa: F401

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _user_id(application, username: str) -> int:
    with application.app_context():
        user = User(username=username, email=f"{username}@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        return user.id


def _headers(application, user_id: int) -> dict[str, str]:
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _zip_payload(contents: dict[str, str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    buffer.seek(0)
    return buffer


def _create_project(client, headers: dict[str, str], name: str = "demo") -> dict:
    response = client.post("/api/security/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json["project"]


def _upload_project(client, headers: dict[str, str], project_id: int, contents: dict[str, str]) -> dict:
    response = client.post(
        f"/api/security/projects/{project_id}/snapshots:upload",
        data={"archive": (_zip_payload(contents), "project.zip")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert response.status_code == 202
    return response.json["task"]


def _find_by_rule(client, headers: dict[str, str], task_id: int, rule_id: str) -> dict:
    response = client.get(f"/api/security/tasks/{task_id}/findings", headers=headers)
    assert response.status_code == 200
    return next(item for item in response.json["items"] if item["rule_id"] == rule_id)


def test_knowledge_source_and_versioned_document_api_are_governed_and_audited(api_app):
    owner = _user_id(api_app, "owner")
    client = api_app.test_client()
    headers = _headers(api_app, owner)

    source_response = client.post(
        "/api/security/knowledge/sources",
        json={
            "name": "OWASP ASVS",
            "source_type": "standard",
            "source_version": "5.0",
            "source_uri": "https://owasp.org/www-project-application-security-verification-standard/",
            "license_name": "CC BY-SA 4.0",
        },
        headers=headers,
    )

    assert source_response.status_code == 201
    source = source_response.json["source"]
    assert source["name"] == "OWASP ASVS"
    assert "metadata" not in source

    document_response = client.post(
        f"/api/security/knowledge/sources/{source['id']}/documents",
        json={
            "document_version": "5.0-v5.3",
            "title": "Command injection prevention",
            "summary": "Prefer argument vectors over shell parsing.",
            "content": "Use parameterized process invocation and avoid shell execution.",
            "tags": ["owasp", "command-injection"],
        },
        headers=headers,
    )

    assert document_response.status_code == 201
    document = document_response.json["document"]
    assert document["title"] == "Command injection prevention"
    assert "content" not in document

    list_response = client.get(f"/api/security/knowledge/sources/{source['id']}/documents", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json["items"][0]["id"] == document["id"]
    assert "content" not in list_response.json["items"][0]

    with api_app.app_context():
        actions = {event.action for event in AuditEvent.query.order_by(AuditEvent.id).all()}
        assert {"knowledge.source_created", "knowledge.document_created"}.issubset(actions)


def test_knowledge_document_api_denies_another_workspace_member(api_app):
    owner = _user_id(api_app, "owner")
    intruder = _user_id(api_app, "intruder")
    with api_app.app_context():
        workspace = Workspace(name="Private Security", slug="private-security")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner, role="owner"))
        source = SecurityKnowledgeSource(
            workspace_id=workspace.id,
            name="Private standard",
            source_type="internal",
            source_version="1",
        )
        db.session.add(source)
        db.session.commit()
        source_id = source.id

    response = api_app.test_client().get(
        f"/api/security/knowledge/sources/{source_id}/documents",
        headers=_headers(api_app, intruder),
    )

    assert response.status_code == 403
    assert response.json == {"error": "无权访问该工作区"}


def test_fallback_suggestion_review_and_audit_api_flow(api_app):
    owner = _user_id(api_app, "owner")
    client = api_app.test_client()
    headers = _headers(api_app, owner)
    project = _create_project(client, headers)
    task = _upload_project(
        client,
        headers,
        project["id"],
        {"app.py": "from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)\n"},
    )
    finding = _find_by_rule(client, headers, task["id"], "PY-FLASK-DEBUG")

    suggestion_response = client.post(
        f"/api/security/findings/{finding['id']}/suggestions",
        headers=headers,
    )

    assert suggestion_response.status_code == 201
    suggestion = suggestion_response.json["suggestion"]
    assert suggestion["provider"] == "rule-based"
    assert "LLM_DISABLED" in suggestion["warning_codes"]
    assert "debug=False" in suggestion["patch_diff"]
    assert suggestion["review_state"] == "pending"

    review_response = client.post(
        f"/api/security/suggestions/{suggestion['id']}/review",
        json={"review_state": "accepted", "comment": "Verified in staging."},
        headers=headers,
    )

    assert review_response.status_code == 200
    assert review_response.json["suggestion"]["review_state"] == "accepted"
    assert review_response.json["suggestion"]["reviewer_id"] == owner

    invalid_review = client.post(
        f"/api/security/suggestions/{suggestion['id']}/review",
        json={"review_state": "auto_applied"},
        headers=headers,
    )
    assert invalid_review.status_code == 400

    list_response = client.get(f"/api/security/findings/{finding['id']}/suggestions", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json["items"][0]["id"] == suggestion["id"]

    with api_app.app_context():
        actions = {event.action for event in AuditEvent.query.order_by(AuditEvent.id).all()}
        assert {"remediation.generated", "remediation.reviewed"}.issubset(actions)


def test_suggestion_generation_is_workspace_scoped_and_secret_payload_stays_redacted(api_app):
    owner = _user_id(api_app, "owner")
    intruder = _user_id(api_app, "intruder")
    client = api_app.test_client()
    owner_headers = _headers(api_app, owner)
    project = _create_project(client, owner_headers, name="private")
    secret = "super-secret-value-123456789"
    task = _upload_project(client, owner_headers, project["id"], {"settings.py": f'API_KEY = "{secret}"\n'})
    finding = _find_by_rule(client, owner_headers, task["id"], "GENERIC-HARDCODED-SECRET")

    denied = client.post(
        f"/api/security/findings/{finding['id']}/suggestions",
        headers=_headers(api_app, intruder),
    )
    assert denied.status_code == 403

    generated = client.post(
        f"/api/security/findings/{finding['id']}/suggestions",
        headers=owner_headers,
    )
    assert generated.status_code == 201
    assert secret.encode("utf-8") not in generated.data
    assert generated.json["suggestion"]["patch_diff"] is None
    assert "RULE_BASED_NO_PATCH" in generated.json["suggestion"]["warning_codes"]
