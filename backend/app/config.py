from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DEFAULT_APP_ENV = "development"
DEFAULT_CORS_ALLOWED_ORIGINS = ("http://localhost:5173",)
DEFAULT_SECRET_PLACEHOLDER = "change-this-secret-key-in-production"
DEFAULT_JWT_SECRET_PLACEHOLDER = "change-this-jwt-secret-key-in-production"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


def _env_list(name: str, default: tuple[str, ...]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_origin(origin: str) -> str:
    parsed = urlparse(origin.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid CORS origin: {origin!r}")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError(f"Invalid CORS origin: {origin!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_cors_origins(origins: Any) -> list[str]:
    if origins is None:
        return []
    if isinstance(origins, str):
        raw_origins = [item.strip() for item in origins.split(",") if item.strip()]
    else:
        raw_origins = [str(item).strip() for item in origins if str(item).strip()]

    normalized: list[str] = []
    for origin in raw_origins:
        if origin == "*":
            raise ValueError("CORS_ALLOWED_ORIGINS cannot contain a wildcard entry")
        normalized.append(_normalize_origin(origin))

    deduped: list[str] = []
    for origin in normalized:
        if origin not in deduped:
            deduped.append(origin)
    return deduped


class Config:
    """Flask application configuration."""

    APP_ENV = os.getenv("APP_ENV", DEFAULT_APP_ENV).strip().lower()
    DEBUG = APP_ENV in {"development", "local", "testing"}
    TESTING = APP_ENV == "testing"

    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_PLACEHOLDER)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET_PLACEHOLDER)
    JWT_ACCESS_TOKEN_EXPIRES = 86400

    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "cyberguard")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@"
        f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen-plus")

    MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
    MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")
    MINIMAX_API_BASE = os.getenv("MINIMAX_API_BASE", "https://api.minimax.chat/v1")

    CHROMA_PERSIST_DIRECTORY = str(DATA_DIR / "chroma_db")

    VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "10"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.5"))
    MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
    EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"

    GRAPH_MAX_HOPS = int(os.getenv("GRAPH_MAX_HOPS", "3"))
    GRAPH_WEIGHT_DECAY = float(os.getenv("GRAPH_WEIGHT_DECAY", "0.8"))

    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

    SECBERT_MODEL = os.getenv("SECBERT_MODEL", "shibing624/text2vec-base-chinese")
    HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
    VECTOR_WEIGHT = float(os.getenv("VECTOR_WEIGHT", "0.7"))
    GRAPH_WEIGHT = float(os.getenv("GRAPH_WEIGHT", "0.3"))

    UPLOAD_FOLDER = str(DATA_DIR / "uploads")
    ARCHIVE_MAX_UPLOAD_BYTES = _env_int("ARCHIVE_MAX_UPLOAD_BYTES", 50 * 1024 * 1024)
    ARCHIVE_MAX_EXTRACT_BYTES = _env_int("ARCHIVE_MAX_EXTRACT_BYTES", 500 * 1024 * 1024)
    ARCHIVE_MAX_FILES = _env_int("ARCHIVE_MAX_FILES", 20000)
    ARCHIVE_MAX_DEPTH = _env_int("ARCHIVE_MAX_DEPTH", 10)
    MAX_CONTENT_LENGTH = ARCHIVE_MAX_UPLOAD_BYTES
    ALLOWED_EXTENSIONS = {"txt", "md", "json", "pdf"}

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = str(DATA_DIR / "logs" / "app.log")

    SECURITY_WORKSPACE_ROOT = os.getenv(
        "SECURITY_WORKSPACE_ROOT",
        str(DATA_DIR / "workspaces"),
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RQ_QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "cyberguard-security")
    RQ_ASYNC = _env_bool("RQ_ASYNC", False)

    CORS_ALLOWED_ORIGINS = normalize_cors_origins(
        _env_list("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS)
    )
    CORS_ORIGINS = CORS_ALLOWED_ORIGINS

    @staticmethod
    def _is_strong_secret(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        secret = value.strip()
        if len(secret) < 32:
            return False
        return secret not in {
            DEFAULT_SECRET_PLACEHOLDER,
            DEFAULT_JWT_SECRET_PLACEHOLDER,
            "your-secret-key-change-in-production",
            "jwt-secret-key-change-in-production",
        }

    @classmethod
    def validate_security_settings(cls, settings: Mapping[str, Any] | None = None) -> None:
        configuration = settings if settings is not None else {
            "APP_ENV": cls.APP_ENV,
            "SECRET_KEY": cls.SECRET_KEY,
            "JWT_SECRET_KEY": cls.JWT_SECRET_KEY,
            "CORS_ALLOWED_ORIGINS": cls.CORS_ALLOWED_ORIGINS,
            "SECURITY_WORKSPACE_ROOT": cls.SECURITY_WORKSPACE_ROOT,
            "REDIS_URL": cls.REDIS_URL,
            "RQ_QUEUE_NAME": cls.RQ_QUEUE_NAME,
            "RQ_ASYNC": cls.RQ_ASYNC,
            "ARCHIVE_MAX_UPLOAD_BYTES": cls.ARCHIVE_MAX_UPLOAD_BYTES,
            "ARCHIVE_MAX_EXTRACT_BYTES": cls.ARCHIVE_MAX_EXTRACT_BYTES,
            "ARCHIVE_MAX_FILES": cls.ARCHIVE_MAX_FILES,
            "ARCHIVE_MAX_DEPTH": cls.ARCHIVE_MAX_DEPTH,
        }

        def setting(name: str, default: Any = "") -> Any:
            return configuration.get(name, default)

        app_env = str(setting("APP_ENV")).strip().lower()
        if app_env not in {"development", "local", "testing", "staging", "production", "prod"}:
            raise ValueError(
                "APP_ENV must be one of development, local, testing, staging, production, prod"
            )

        origins = normalize_cors_origins(setting("CORS_ALLOWED_ORIGINS", []))
        if not origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain at least one explicit origin")

        if app_env in {"production", "prod"}:
            if not cls._is_strong_secret(setting("SECRET_KEY")):
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and not use a placeholder in production"
                )
            if not cls._is_strong_secret(setting("JWT_SECRET_KEY")):
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters and not use a placeholder in production"
                )

        workspace_root = Path(str(setting("SECURITY_WORKSPACE_ROOT"))).expanduser()
        if not workspace_root.is_absolute():
            workspace_root = BASE_DIR / workspace_root
        workspace_root = workspace_root.resolve()
        if workspace_root == Path(workspace_root.anchor):
            raise ValueError("SECURITY_WORKSPACE_ROOT must not point to a filesystem root")

        queue_name = str(setting("RQ_QUEUE_NAME")).strip()
        if not queue_name:
            raise ValueError("RQ_QUEUE_NAME must not be empty")

        rq_async_value = setting("RQ_ASYNC", False)
        rq_async = (
            rq_async_value.strip().lower() in {"1", "true", "yes", "on"}
            if isinstance(rq_async_value, str)
            else bool(rq_async_value)
        )
        if rq_async:
            redis_url = str(setting("REDIS_URL")).strip()
            parsed = urlparse(redis_url)
            if parsed.scheme not in {"redis", "rediss"} or not parsed.netloc:
                raise ValueError(
                    "REDIS_URL must be a redis:// or rediss:// URL when RQ_ASYNC is enabled"
                )

        upload_limit = int(setting("ARCHIVE_MAX_UPLOAD_BYTES", 0))
        extract_limit = int(setting("ARCHIVE_MAX_EXTRACT_BYTES", 0))
        file_limit = int(setting("ARCHIVE_MAX_FILES", 0))
        depth_limit = int(setting("ARCHIVE_MAX_DEPTH", 0))
        if upload_limit <= 0:
            raise ValueError("ARCHIVE_MAX_UPLOAD_BYTES must be positive")
        if extract_limit <= 0:
            raise ValueError("ARCHIVE_MAX_EXTRACT_BYTES must be positive")
        if file_limit <= 0:
            raise ValueError("ARCHIVE_MAX_FILES must be positive")
        if depth_limit <= 0:
            raise ValueError("ARCHIVE_MAX_DEPTH must be positive")
        if extract_limit < upload_limit:
            raise ValueError("ARCHIVE_MAX_EXTRACT_BYTES must be greater than or equal to ARCHIVE_MAX_UPLOAD_BYTES")

