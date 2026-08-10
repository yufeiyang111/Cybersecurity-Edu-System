from pathlib import Path
import os
import sys
import types

import pytest
from flask import Blueprint
from sqlalchemy import event

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 测试隔离：禁止读取开发 .env 中的 API 开关（load_dotenv 不覆盖已有环境变量）
os.environ.setdefault("SILICONFLOW_API_KEY", "")
os.environ.setdefault("EMBEDDING_API_KEY", "")
os.environ.setdefault("RERANKER_API_KEY", "")
os.environ.setdefault("EMBEDDING_API_ENABLED", "false")
os.environ.setdefault("RERANKER_API_ENABLED", "false")
os.environ.setdefault("RERANK_ENABLED", "false")


class TestConfig:
    APP_ENV = "testing"
    DEBUG = False
    TESTING = True
    SECRET_KEY = "a" * 32
    JWT_SECRET_KEY = "b" * 32
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ALLOWED_ORIGINS = ["https://security.example.test"]
    SECURITY_WORKSPACE_ROOT = "security-workspaces"
    REDIS_URL = "redis://localhost:6379/0"
    RQ_QUEUE_NAME = "cyberguard-security-test"
    RQ_ASYNC = False
    GITHUB_API_TIMEOUT_SECONDS = 15
    GITHUB_MAX_REDIRECTS = 1
    SCA_OSV_ENABLED = False
    SCA_OSV_API_URL = "https://api.osv.dev/v1/querybatch"
    SCA_REQUEST_TIMEOUT_SECONDS = 15
    SCA_CACHE_TTL_SECONDS = 86400
    SCA_MAX_DEPENDENCIES = 10000
    ARCHIVE_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
    ARCHIVE_MAX_EXTRACT_BYTES = 500 * 1024 * 1024
    ARCHIVE_MAX_FILES = 20_000
    ARCHIVE_MAX_DEPTH = 10
    UPLOAD_FOLDER = "uploads"
    LOG_FILE = "logs/test.log"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
    }


_ROUTE_STUB_MODULES = {
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
}

# legacy stub 不含 projects / help，两者需从磁盘真实加载：
# - app.routes.projects：security 路由 facade（agent 等测试依赖）
# - app.routes.help：帮助中心路由
_ROUTE_STUB_MODULES_LEGACY = dict(_ROUTE_STUB_MODULES)
del _ROUTE_STUB_MODULES_LEGACY["app.routes.projects"]
del _ROUTE_STUB_MODULES_LEGACY["app.routes.help"]


def _install_route_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    routes_package = types.ModuleType("app.routes")
    routes_package.__path__ = []
    monkeypatch.setitem(sys.modules, "app.routes", routes_package)

    for module_name, blueprint_name in _ROUTE_STUB_MODULES.items():
        module = types.ModuleType(module_name)
        blueprint = Blueprint(blueprint_name, module_name)
        setattr(module, blueprint_name, blueprint)
        if module_name == "app.routes.oauth":
            setattr(module, "init_oauth", lambda app: None)
        monkeypatch.setitem(sys.modules, module_name, module)


def _install_legacy_route_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub only legacy route modules; real security routes stay loaded.

    The synthetic ``app.routes`` package keeps the real filesystem path so
    ``app.routes.projects`` (security facade) loads from disk, but skips the
    heavy ``app/routes/__init__.py`` imports.
    """
    routes_dir = Path(__file__).resolve().parents[1] / "app" / "routes"
    routes_package = types.ModuleType("app.routes")
    routes_package.__path__ = [str(routes_dir)]
    monkeypatch.setitem(sys.modules, "app.routes", routes_package)

    for module_name, blueprint_name in _ROUTE_STUB_MODULES_LEGACY.items():
        module = types.ModuleType(module_name)
        blueprint = Blueprint(blueprint_name, module_name)
        setattr(module, blueprint_name, blueprint)
        if module_name == "app.routes.oauth":
            setattr(module, "init_oauth", lambda app: None)
        monkeypatch.setitem(sys.modules, module_name, module)


@pytest.fixture
def agent_api_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """API fixture with real security routes and a file-backed sqlite database.

    The agent executor runs synchronously (AGENT_RUN_EXECUTOR=synchronous)
    so create responses are deterministic without background threads.
    """
    from app import create_app, db

    import app.models

    _install_legacy_route_stubs(monkeypatch)
    config = type(
        "AgentApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "security-workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "AGENT_LOG_FILE": str(tmp_path / "logs" / "agent.log"),
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'agent_api.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
            "AGENT_RUN_EXECUTOR": "synchronous",
            "AGENT_MIN_STEP_INTERVAL_SECONDS": 0,
            "RQ_ASYNC": False,
        },
    )
    application = create_app(config)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app, db
    import app.models  # Ensure db.create_all() sees all registered application models.

    _install_route_stubs(monkeypatch)
    config = type(
        "TestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "security-workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "AGENT_LOG_FILE": str(tmp_path / "logs" / "agent.log"),
        },
    )
    application = create_app(config)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()