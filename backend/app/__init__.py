"""CyberGuard application factory."""

from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from app.config import Config, DATA_DIR, normalize_cors_origins
from app.services.observability import register_request_context


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
    workspace_root = Path(app.config["SECURITY_WORKSPACE_ROOT"]).expanduser()
    if not workspace_root.is_absolute():
        workspace_root = (DATA_DIR.parent / workspace_root).resolve()
    app.config["SECURITY_WORKSPACE_ROOT"] = str(workspace_root)
    _ensure_directory(workspace_root)

    db.init_app(app)
    jwt.init_app(app)
    register_request_context(app)
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

    return app


