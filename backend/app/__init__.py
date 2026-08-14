"""CyberGuard application factory."""

from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from app.config import Config, DATA_DIR, normalize_cors_origins
from app.services.observability import (
    register_rag_runtime_metrics,
    register_request_context,
)


db = SQLAlchemy()
jwt = JWTManager()
from app.services.runtime_health import liveness_payload, readiness_payload


def _ensure_directory(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def create_app(config_object: type | None = None) -> Flask:
    from app.utils.proxy import normalize_system_proxy_env

    normalize_system_proxy_env()
    app = Flask(__name__)
    active_config = config_object or Config
    app.config.from_object(active_config)

    Config.validate_security_settings(app.config)

    allowed_origins = normalize_cors_origins(app.config.get("CORS_ALLOWED_ORIGINS", []))
    app.config["CORS_ALLOWED_ORIGINS"] = allowed_origins
    app.config["CORS_ORIGINS"] = allowed_origins

    _ensure_directory(DATA_DIR)
    _ensure_directory(app.config["UPLOAD_FOLDER"])
    _ensure_directory(Path(app.config["LOG_FILE"]).parent)
    from app.services.agent_observability import configure_agent_logger

    configure_agent_logger(app)
    workspace_root = Path(app.config["SECURITY_WORKSPACE_ROOT"]).expanduser()
    if not workspace_root.is_absolute():
        workspace_root = (DATA_DIR.parent / workspace_root).resolve()
    app.config["SECURITY_WORKSPACE_ROOT"] = str(workspace_root)
    _ensure_directory(workspace_root)

    db.init_app(app)
    jwt.init_app(app)
    register_request_context(app)
    register_rag_runtime_metrics(app)
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    try:
        from flasgger import Swagger

        from app.swagger_config import SWAGGER_CONFIG, SWAGGER_TEMPLATE

        Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
    except ImportError:
        app.logger.warning("Swagger setup skipped because flasgger is not installed")

    from app.routes.auth import auth_bp
    from app.routes.auth_preferences import auth_preferences_bp
    from app.routes.oauth import oauth_bp, init_oauth
    from app.routes.knowledge import knowledge_bp
    from app.routes.qa import qa_bp
    from app.routes.admin import admin_bp
    from app.routes.projects import projects_bp
    from app.routes.llm_health import llm_health_bp
    from app.routes.llm import llm_bp
    from app.routes.policies import policies_bp
    from app.routes.memories import memories_bp
    from app.routes.help import help_bp
    from app.routes.user_activity import user_activity_bp
    from app.routes.admin_users import admin_users_bp
    from app.routes.admin_vector import admin_vector_bp
    from app.routes.admin_graph import admin_graph_bp
    from app.routes.admin_rag import admin_rag_bp

    init_oauth(app)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(auth_preferences_bp, url_prefix="/api/auth")
    app.register_blueprint(oauth_bp, url_prefix="/api/auth")
    app.register_blueprint(knowledge_bp, url_prefix="/api/knowledge")
    app.register_blueprint(qa_bp, url_prefix="/api/qa")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(projects_bp, url_prefix="/api/security")
    app.register_blueprint(llm_health_bp, url_prefix="/api/health")
    app.register_blueprint(llm_bp, url_prefix="/api/llm")
    app.register_blueprint(policies_bp, url_prefix="/api")
    app.register_blueprint(memories_bp, url_prefix="/api")
    app.register_blueprint(help_bp, url_prefix="/api")
    app.register_blueprint(user_activity_bp, url_prefix="/api/user")
    app.register_blueprint(admin_users_bp, url_prefix="/api/admin")
    app.register_blueprint(admin_vector_bp, url_prefix="/api/admin")
    app.register_blueprint(admin_graph_bp, url_prefix="/api/admin")
    app.register_blueprint(admin_rag_bp, url_prefix="/api/admin")

    # 后台预热 RAG 引擎：加载 embedding 模型耗时长且占用内存大（bge-m3 约 1.8GB），
    # 延迟启动避免加载高峰与用户请求（如登录）争抢内存，同时避免首次相关推荐请求变慢
    if app.config.get("APP_ENV") != "testing":
        import threading

        def _warmup_rag_engine() -> None:
            try:
                from app.services.rag_engine import get_rag_engine

                get_rag_engine()
            except Exception:
                app.logger.exception("RAG 引擎后台预热失败")
            # RERANK_ENABLED 开启时预热真实 rerank 模型，避免首次 QA 请求现场加载
            if app.config.get("RERANK_ENABLED"):
                try:
                    from app.services.llm.reranker_service import get_reranker_service

                    get_reranker_service()._load()
                except Exception:
                    app.logger.warning("reranker 预热失败，首次问答将现场加载或降级")

        warmup_timer = threading.Timer(10.0, _warmup_rag_engine)
        warmup_timer.daemon = True
        warmup_timer.name = "rag-engine-warmup"
        warmup_timer.start()

    @app.errorhandler(404)
    def api_not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "资源不存在"}), 404
        return error

    @app.errorhandler(500)
    def api_internal_error(error):
        if request.path.startswith("/api/"):
            app.logger.exception("未处理的 API 异常")
            return jsonify({"error": "服务器内部错误"}), 500
        return error

    @app.route("/api/health")
    def health() -> dict[str, str]:
        return liveness_payload()

    @app.route("/api/health/live")
    def health_live() -> dict[str, str]:
        return liveness_payload()

    @app.route("/api/health/ready")
    def health_ready():
        payload = readiness_payload(app.config)
        return payload, 200 if payload["status"] == "ready" else 503

    from app.services.security_agent.watchdog import register_watchdog_commands

    register_watchdog_commands(app)

    return app


