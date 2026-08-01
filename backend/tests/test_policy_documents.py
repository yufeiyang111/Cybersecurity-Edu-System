from __future__ import annotations

import sys
import types

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.user import User
from app.services import policy_service


def _install_legacy_route_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.routes

    for module_name, blueprint_name in {
        "app.routes.auth": "auth_bp",
        "app.routes.knowledge": "knowledge_bp",
        "app.routes.qa": "qa_bp",
        "app.routes.admin": "admin_bp",
        "app.routes.projects": "projects_bp",
        "app.routes.llm_health": "llm_health_bp",
    }.items():
        module = types.ModuleType(module_name)
        setattr(module, blueprint_name, Blueprint(blueprint_name, module_name))
        monkeypatch.setitem(sys.modules, module_name, module)


@pytest.fixture
def policy_app(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    from conftest import TestConfig

    _install_legacy_route_stubs(monkeypatch)
    config = type(
        "PolicyApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
        },
    )
    application = create_app(config)
    with application.app_context():
        import app.models  # noqa: F401

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _make_user(application, username: str, role: str) -> int:
    with application.app_context():
        user = User(username=username, email=f"{username}@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    token = create_access_token(identity=str(user_id), additional_claims={"role": role})
    return user_id, {"Authorization": f"Bearer {token}"}


def test_policies_list_is_public_and_seeded(policy_app):
    response = policy_app.test_client().get("/api/policies")

    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json["policies"]}
    assert slugs == {"terms", "privacy"}
    assert all("content" not in item for item in response.json["policies"])


def test_get_policy_returns_markdown_content(policy_app):
    response = policy_app.test_client().get("/api/policies/terms")

    assert response.status_code == 200
    policy = response.json["policy"]
    assert policy["title"] == "用户协议"
    assert policy["slug"] == "terms"
    assert policy["version"] == 1
    assert policy["content"].startswith("#")


def test_get_unknown_policy_returns_404(policy_app):
    response = policy_app.test_client().get("/api/policies/unknown")

    assert response.status_code == 404


def test_update_requires_authentication(policy_app):
    response = policy_app.test_client().put(
        "/api/policies/terms",
        json={"title": "新标题", "content": "新内容"},
    )

    assert response.status_code == 401


def test_update_rejects_non_admin(policy_app):
    _, headers = _make_user(policy_app, "regular-user", "user")
    response = policy_app.test_client().put(
        "/api/policies/terms",
        json={"title": "新标题", "content": "新内容"},
        headers=headers,
    )

    assert response.status_code == 403


def test_update_rejects_empty_content(policy_app):
    _, headers = _make_user(policy_app, "admin-user", "admin")
    response = policy_app.test_client().put(
        "/api/policies/terms",
        json={"title": "新标题", "content": "   "},
        headers=headers,
    )

    assert response.status_code == 400


def test_admin_update_increments_version_and_records_updater(policy_app):
    _, headers = _make_user(policy_app, "admin-user", "admin")
    response = policy_app.test_client().put(
        "/api/policies/terms",
        json={"title": "新版用户协议", "content": "## 新版正文\n\n内容已更新。"},
        headers=headers,
    )

    assert response.status_code == 200
    policy = response.json["policy"]
    assert policy["title"] == "新版用户协议"
    assert policy["version"] == 2
    assert policy["updated_by"] == "admin-user"

    fetch = policy_app.test_client().get("/api/policies/terms")
    assert fetch.json["policy"]["version"] == 2


def test_update_unknown_slug_returns_404(policy_app):
    _, headers = _make_user(policy_app, "admin-user", "admin")
    response = policy_app.test_client().put(
        "/api/policies/nope",
        json={"title": "标题", "content": "内容"},
        headers=headers,
    )

    assert response.status_code == 404


def test_service_update_creates_document_for_new_slug(policy_app):
    with policy_app.app_context():
        created = policy_service.update_policy("faq", "常见问题", "## FAQ", "tester")

        assert created.slug == "faq"
        assert created.version == 1
        assert created.updated_by == "tester"
