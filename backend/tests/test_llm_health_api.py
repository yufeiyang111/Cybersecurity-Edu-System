from __future__ import annotations

import sys
import types

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.user import User
from app.services.llm import LLMResponse
from app.services.llm.health import LLMProviderHealthChecker


def _install_legacy_route_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.routes

    for module_name, blueprint_name in {
        "app.routes.auth": "auth_bp",
        "app.routes.knowledge": "knowledge_bp",
        "app.routes.qa": "qa_bp",
        "app.routes.admin": "admin_bp",
        "app.routes.projects": "projects_bp",
    }.items():
        module = types.ModuleType(module_name)
        setattr(module, blueprint_name, Blueprint(blueprint_name, module_name))
        monkeypatch.setitem(sys.modules, module_name, module)


@pytest.fixture
def health_api_app(tmp_path, monkeypatch):
    from conftest import TestConfig

    _install_legacy_route_stubs(monkeypatch)
    config = type(
        "HealthApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "MINIMAX_API_KEY": "",
            "MINIMAX_MODEL": "MiniMax-test",
            "DASHSCOPE_API_KEY": "",
            "DASHSCOPE_MODEL": "qwen-test",
        },
    )
    application = create_app(config)
    from app.routes import llm_health

    application.extensions.pop(llm_health._HEALTH_CHECKER_EXTENSION, None)
    with application.app_context():
        import app.models

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
    llm_health._health_checker = None


def _auth_headers(application, user_id: int) -> dict[str, str]:
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _make_user(application) -> int:
    with application.app_context():
        user = User(username="health-user", email="health-user@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        return user.id


class _HealthyProvider:
    provider_name = "minimax"
    model = "MiniMax-test"
    model_version = "test-version"

    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(
            text="OK",
            provider_name=self.provider_name,
            model=self.model,
            model_version=self.model_version,
            status_code=200,
            latency_ms=7,
        )


def test_llm_health_get_requires_authentication(health_api_app):
    response = health_api_app.test_client().get("/api/health/llm-providers")

    assert response.status_code == 401


def test_llm_health_get_is_passive_and_returns_safe_configuration_state(health_api_app):
    user_id = _make_user(health_api_app)
    response = health_api_app.test_client().get(
        "/api/health/llm-providers",
        headers=_auth_headers(health_api_app, user_id),
    )

    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json["providers"]}
    assert set(providers) == {"minimax", "dashscope"}
    assert providers["minimax"]["configured"] is False
    assert providers["minimax"]["reachable"] is None
    assert providers["minimax"]["warning_code"] == "LLM_PROVIDER_NOT_CONFIGURED"
    assert "api_key" not in response.get_data(as_text=True).lower()
    assert "api_base" not in response.get_data(as_text=True).lower()


def test_llm_health_post_runs_only_explicit_injected_live_check(health_api_app, monkeypatch):
    user_id = _make_user(health_api_app)
    provider = _HealthyProvider()
    checker = LLMProviderHealthChecker(
        config={"MINIMAX_API_KEY": "secret-key", "MINIMAX_MODEL": "MiniMax-test"},
        provider_factories={"minimax": lambda: provider},
        sdk_checkers={"minimax": lambda: True},
        cooldown_seconds=0,
    )
    from app.routes import llm_health

    monkeypatch.setattr(llm_health, "get_health_checker", lambda: checker)
    response = health_api_app.test_client().post(
        "/api/health/llm-providers/minimax/check",
        headers=_auth_headers(health_api_app, user_id),
    )

    assert response.status_code == 200
    payload = response.json["provider"]
    assert payload["status"] == "healthy"
    assert payload["reachable"] is True
    assert payload["latency_ms"] == 7
    assert "secret-key" not in response.get_data(as_text=True)
    assert len(provider.requests) == 1


def test_llm_health_post_rejects_unsupported_provider(health_api_app):
    user_id = _make_user(health_api_app)
    response = health_api_app.test_client().post(
        "/api/health/llm-providers/unknown/check",
        headers=_auth_headers(health_api_app, user_id),
    )

    assert response.status_code == 400
    assert response.json["provider"]["warning_code"] == "LLM_PROVIDER_UNSUPPORTED"
