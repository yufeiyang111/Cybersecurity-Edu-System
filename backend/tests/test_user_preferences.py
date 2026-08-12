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


def test_preferences_qa_max_tokens_accepted_and_persisted(preferences_app):
    user_id = _make_user(preferences_app)
    response = preferences_app.test_client().put(
        "/api/auth/preferences",
        json={"qa_max_tokens": 8192},
        headers=_auth_headers(preferences_app, user_id),
    )
    assert response.status_code == 200
    assert response.json["preferences"]["qa_max_tokens"] == 8192

    with preferences_app.app_context():
        stored = UserPreference.query.filter_by(user_id=user_id).one()
        assert stored.qa_max_tokens == 8192


def test_preferences_qa_max_tokens_null_resets_to_default(preferences_app):
    user_id = _make_user(preferences_app)
    headers = _auth_headers(preferences_app, user_id)
    client = preferences_app.test_client()
    assert client.put("/api/auth/preferences", json={"qa_max_tokens": 4096}, headers=headers).status_code == 200
    assert client.put("/api/auth/preferences", json={"qa_max_tokens": None}, headers=headers).status_code == 200
    assert client.put("/api/auth/preferences", json={"qa_max_tokens": None}, headers=headers).json["preferences"]["qa_max_tokens"] is None


def test_preferences_qa_max_tokens_reject_invalid(preferences_app):
    user_id = _make_user(preferences_app)
    headers = _auth_headers(preferences_app, user_id)
    for invalid in (0, -1, 384001, 500000, "8192", True, 1.5):
        response = preferences_app.test_client().put(
            "/api/auth/preferences",
            json={"qa_max_tokens": invalid},
            headers=headers,
        )
        assert response.status_code == 400, f"qa_max_tokens={invalid!r} 应被拒绝"


def test_preferences_analytics_defaults_and_validation(preferences_app):
    user_id = _make_user(preferences_app)
    client = preferences_app.test_client()
    headers = _auth_headers(preferences_app, user_id)

    initial = client.get("/api/auth/preferences", headers=headers)
    assert initial.status_code == 200
    prefs = initial.json["preferences"]
    assert prefs["analytics_time_range"] == "1d"
    assert prefs["analytics_time_granularity"] == "hour"
    assert prefs["analytics_chart_type"] == "bar"
    assert prefs["analytics_model_chart"] == "trend"

    updated = client.put(
        "/api/auth/preferences",
        json={
            "analytics_time_range": "7d",
            "analytics_time_granularity": "day",
            "analytics_chart_type": "area",
            "analytics_model_chart": "ranking",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    prefs = updated.json["preferences"]
    assert prefs["analytics_time_range"] == "7d"
    assert prefs["analytics_time_granularity"] == "day"
    assert prefs["analytics_chart_type"] == "area"
    assert prefs["analytics_model_chart"] == "ranking"

    with preferences_app.app_context():
        stored = UserPreference.query.filter_by(user_id=user_id).one()
        assert stored.analytics_time_range == "7d"
        assert stored.analytics_time_granularity == "day"
        assert stored.analytics_chart_type == "area"
        assert stored.analytics_model_chart == "ranking"


def test_preferences_analytics_reject_invalid_values(preferences_app):
    user_id = _make_user(preferences_app)
    headers = _auth_headers(preferences_app, user_id)
    for payload in (
        {"analytics_time_range": "2w"},
        {"analytics_time_range": "30d"},
        {"analytics_time_granularity": "quarter"},
        {"analytics_chart_type": "pie"},
        {"analytics_model_chart": "table"},
    ):
        response = preferences_app.test_client().put(
            "/api/auth/preferences",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 400, f"{payload!r} 应被拒绝"
