import sys
import types

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.user import User, UserPreference


@pytest.fixture
def preferences_app(monkeypatch, tmp_path):
    from conftest import TestConfig
    for module_name, blueprint_name in {
        "app.routes.knowledge": "knowledge_bp",
        "app.routes.qa": "qa_bp",
        "app.routes.admin": "admin_bp",
        "app.routes.oauth": "oauth_bp",
        "app.routes.projects": "projects_bp",
        "app.routes.llm_health": "llm_health_bp",
        "app.routes.policies": "policies_bp",
    }.items():
        module = types.ModuleType(module_name)
        setattr(module, blueprint_name, Blueprint(blueprint_name, __name__))
        if module_name.endswith("oauth"):
            module.init_oauth = lambda _application: None
        monkeypatch.setitem(sys.modules, module_name, module)
    config = type("PreferencesTestConfig", (TestConfig,), {
        "LOG_FILE": str(tmp_path / "logs" / "test.log"),
    })
    application = create_app(config)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_headers(application, user_id):
    with application.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _make_user(application):
    with application.app_context():
        user = User(username="preferences-user", email="preferences@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_preferences_are_created_and_updated(preferences_app):
    user_id = _make_user(preferences_app)
    client = preferences_app.test_client()
    headers = _auth_headers(preferences_app, user_id)

    initial = client.get("/api/auth/preferences", headers=headers)
    assert initial.status_code == 200
    assert initial.json["preferences"]["theme"] == "system"

    response = client.put(
        "/api/auth/preferences",
        json={"theme": "dark", "color_preset": "lake", "language": "en", "custom_prompt": "回答时先给结论。"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json["preferences"]["theme"] == "dark"
    assert response.json["preferences"]["color_preset"] == "lake"
    assert response.json["preferences"]["custom_prompt"] == "回答时先给结论。"

    with preferences_app.app_context():
        stored = UserPreference.query.filter_by(user_id=user_id).one()
        assert stored.language == "en"


def test_preferences_reject_invalid_values(preferences_app):
    user_id = _make_user(preferences_app)
    response = preferences_app.test_client().put(
        "/api/auth/preferences",
        json={"language": "xx"},
        headers=_auth_headers(preferences_app, user_id),
    )
    assert response.status_code == 400
