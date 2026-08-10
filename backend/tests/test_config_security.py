from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from flask import Blueprint

from app import create_app
from app.config import Config


ALLOWED_ORIGIN = "https://security.example.com"


def _install_route_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    routes_package = types.ModuleType("app.routes")
    routes_package.__path__ = []
    monkeypatch.setitem(sys.modules, "app.routes", routes_package)

    for module_name, blueprint_name in {
        "app.routes.auth": "auth_bp",
        "app.routes.auth_preferences": "auth_preferences_bp",
        "app.routes.oauth": "oauth_bp",
        "app.routes.knowledge": "knowledge_bp",
        "app.routes.qa": "qa_bp",
        "app.routes.admin": "admin_bp",
        "app.routes.projects": "projects_bp",
        "app.routes.llm_health": "llm_health_bp",
        "app.routes.llm": "llm_bp",
        "app.routes.policies": "policies_bp",
        "app.routes.memories": "memories_bp",
        "app.routes.help": "help_bp",
        "app.routes.user_activity": "user_activity_bp",
        "app.routes.admin_users": "admin_users_bp",
        "app.routes.admin_vector": "admin_vector_bp",
    }.items():
        module = types.ModuleType(module_name)
        blueprint = Blueprint(blueprint_name, module_name)
        setattr(module, blueprint_name, blueprint)
        if module_name == "app.routes.oauth":
            setattr(module, "init_oauth", lambda app: None)
        monkeypatch.setitem(sys.modules, module_name, module)


def _make_config(tmp_path: Path, **overrides):
    base = {
        "APP_ENV": "production",
        "DEBUG": False,
        "TESTING": True,
        "SECRET_KEY": "a" * 32,
        "JWT_SECRET_KEY": "b" * 32,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "CORS_ALLOWED_ORIGINS": [ALLOWED_ORIGIN],
        "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
        "REDIS_URL": "redis://localhost:6379/0",
        "RQ_QUEUE_NAME": "cyberguard-security",
        "RQ_ASYNC": False,
        "ARCHIVE_MAX_UPLOAD_BYTES": 50 * 1024 * 1024,
        "ARCHIVE_MAX_EXTRACT_BYTES": 500 * 1024 * 1024,
        "ARCHIVE_MAX_FILES": 20_000,
        "ARCHIVE_MAX_DEPTH": 10,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "LOG_FILE": str(tmp_path / "logs" / "app.log"),
    }
    base.update(overrides)
    return type("TestConfig", (), base)


def test_create_app_uses_custom_config_and_restricts_cors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_route_stubs(monkeypatch)
    app = create_app(_make_config(tmp_path))

    assert app.config["APP_ENV"] == "production"
    assert app.config["DEBUG"] is False
    assert app.config["CORS_ALLOWED_ORIGINS"] == [ALLOWED_ORIGIN]
    assert app.config["SECURITY_WORKSPACE_ROOT"] == str(tmp_path / "workspaces")
    assert app.config["ARCHIVE_MAX_UPLOAD_BYTES"] == 50 * 1024 * 1024
    assert app.config["ARCHIVE_MAX_EXTRACT_BYTES"] == 500 * 1024 * 1024
    assert app.config["ARCHIVE_MAX_FILES"] == 20_000
    assert app.config["ARCHIVE_MAX_DEPTH"] == 10

    response = app.test_client().get("/api/health", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
    assert (tmp_path / "workspaces").exists()

    blocked = app.test_client().get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert blocked.headers.get("Access-Control-Allow-Origin") is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("CORS_ALLOWED_ORIGINS", ["*"], "CORS_ALLOWED_ORIGINS"),
        ("SECRET_KEY", "change-this-secret-key-in-production", "SECRET_KEY"),
        ("RQ_ASYNC", True, "REDIS_URL"),
    ],
)
def test_validate_security_settings_rejects_insecure_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value,
    message: str,
) -> None:
    _install_route_stubs(monkeypatch)
    kwargs = {field: value}
    if field == "RQ_ASYNC":
        kwargs["REDIS_URL"] = ""
    with pytest.raises(ValueError, match=message):
        create_app(_make_config(tmp_path, **kwargs))


def test_validate_security_settings_rejects_unbounded_scan_retries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_route_stubs(monkeypatch)
    with pytest.raises(ValueError, match="SCAN_TASK_MAX_RETRIES"):
        create_app(_make_config(tmp_path, SCAN_TASK_MAX_RETRIES=11))


def test_validate_security_settings_reads_environment_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    original_environment = Config.APP_ENV
    original_secret = Config.SECRET_KEY
    original_jwt_secret = Config.JWT_SECRET_KEY
    try:
        Config.APP_ENV = "production"
        Config.SECRET_KEY = "change-this-secret-key-in-production"
        Config.JWT_SECRET_KEY = "change-this-jwt-secret-key-in-production"
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Config.validate_security_settings()
    finally:
        Config.APP_ENV = original_environment
        Config.SECRET_KEY = original_secret
        Config.JWT_SECRET_KEY = original_jwt_secret
