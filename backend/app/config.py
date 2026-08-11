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
DEFAULT_GITHUB_API_TIMEOUT_SECONDS = 15
DEFAULT_GITHUB_MAX_REDIRECTS = 1
DEFAULT_SCA_OSV_API_URL = "https://api.osv.dev/v1/querybatch"
DEFAULT_SCA_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_SCA_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_SCA_MAX_DEPENDENCIES = 10_000
MAX_SCA_DEPENDENCIES = 50_000
DEFAULT_REMEDIATION_MAX_CONTEXT_CHARS = 12_000
DEFAULT_REMEDIATION_MAX_OUTPUT_CHARS = 8_000
DEFAULT_REMEDIATION_RETRIEVAL_TOP_K = 5
DEFAULT_REMEDIATION_PATCH_MAX_LINES = 500
DEFAULT_REMEDIATION_PATCH_MAX_CHARS = 50_000
MAX_REMEDIATION_CONTEXT_CHARS = 200_000
MAX_REMEDIATION_OUTPUT_CHARS = 100_000
MAX_REMEDIATION_RETRIEVAL_TOP_K = 50
MAX_REMEDIATION_PATCH_MAX_LINES = 5_000
MAX_REMEDIATION_PATCH_MAX_CHARS = 500_000
DEFAULT_SCAN_TASK_MAX_RETRIES = 3
MAX_SCAN_TASK_MAX_RETRIES = 10
DEFAULT_SECURITY_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE = 10
DEFAULT_LLM_PROVIDER_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_LLM_PROVIDER_READ_TIMEOUT_SECONDS = 60.0
DEFAULT_LLM_PROVIDER_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


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


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw.strip())


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

    # OAuth 第三方登录（Google / GitHub）
    OAUTH_BACKEND_BASE_URL = os.getenv("OAUTH_BACKEND_BASE_URL", "http://localhost:5001")
    OAUTH_FRONTEND_URL = os.getenv("OAUTH_FRONTEND_URL", "http://localhost:5173")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

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
    MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
    MINIMAX_API_BASE = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")

    # LLM 图谱抽取备用 Provider（MiniMax 额度耗尽时自动切换）
    KG_FALLBACK_API_KEY = os.getenv("KG_FALLBACK_API_KEY", "")
    KG_FALLBACK_MODEL = os.getenv("KG_FALLBACK_MODEL", "deepseek-v4-flash")
    KG_FALLBACK_API_BASE = os.getenv("KG_FALLBACK_API_BASE", "https://opencode.ai/zen/go/v1")

    LLM_PROVIDER_ENCRYPTION_KEY = os.getenv("LLM_PROVIDER_ENCRYPTION_KEY", "").strip()
    LLM_PROVIDER_ALLOWED_HOSTS = _env_list("LLM_PROVIDER_ALLOWED_HOSTS", ())
    LLM_PROVIDER_CONNECT_TIMEOUT_SECONDS = _env_float(
        "LLM_PROVIDER_CONNECT_TIMEOUT_SECONDS", DEFAULT_LLM_PROVIDER_CONNECT_TIMEOUT_SECONDS
    )
    LLM_PROVIDER_READ_TIMEOUT_SECONDS = _env_float(
        "LLM_PROVIDER_READ_TIMEOUT_SECONDS", DEFAULT_LLM_PROVIDER_READ_TIMEOUT_SECONDS
    )
    LLM_PROVIDER_MAX_RESPONSE_BYTES = _env_int(
        "LLM_PROVIDER_MAX_RESPONSE_BYTES", DEFAULT_LLM_PROVIDER_MAX_RESPONSE_BYTES
    )
    # LLM 调用自动重试：429/5xx/超时 指数退避（0.8s/1.6s）
    LLM_MAX_RETRIES = _env_int("LLM_MAX_RETRIES", 2)
    LLM_RETRY_BASE_DELAY = _env_float("LLM_RETRY_BASE_DELAY", 0.8)

    CHROMA_PERSIST_DIRECTORY = str(DATA_DIR / "chroma_db")
    VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "qdrant").strip().lower()
    QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip()
    QDRANT_PATH = os.getenv("QDRANT_PATH", str(DATA_DIR / "qdrant_db"))
    SECURITY_KNOWLEDGE_VECTOR_ENABLED = _env_bool("SECURITY_KNOWLEDGE_VECTOR_ENABLED", False)
    REMEDIATION_LLM_ENABLED = _env_bool("REMEDIATION_LLM_ENABLED", False)
    REMEDIATION_LLM_PROVIDER = os.getenv("REMEDIATION_LLM_PROVIDER", "").strip()
    SECURITY_RISK_POLICY = os.getenv("SECURITY_RISK_POLICY", "").strip()
    REMEDIATION_MAX_CONTEXT_CHARS = _env_int(
        "REMEDIATION_MAX_CONTEXT_CHARS", DEFAULT_REMEDIATION_MAX_CONTEXT_CHARS
    )
    REMEDIATION_MAX_OUTPUT_CHARS = _env_int(
        "REMEDIATION_MAX_OUTPUT_CHARS", DEFAULT_REMEDIATION_MAX_OUTPUT_CHARS
    )
    REMEDIATION_RETRIEVAL_TOP_K = _env_int(
        "REMEDIATION_RETRIEVAL_TOP_K", DEFAULT_REMEDIATION_RETRIEVAL_TOP_K
    )
    REMEDIATION_PATCH_MAX_LINES = _env_int(
        "REMEDIATION_PATCH_MAX_LINES", DEFAULT_REMEDIATION_PATCH_MAX_LINES
    )
    REMEDIATION_PATCH_MAX_CHARS = _env_int(
        "REMEDIATION_PATCH_MAX_CHARS", DEFAULT_REMEDIATION_PATCH_MAX_CHARS
    )

    VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "10"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.5"))
    MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
    # QA 高成本 LLM 调用限流（每分钟每用户）
    QA_RATE_LIMIT_PER_MINUTE = _env_int("QA_RATE_LIMIT_PER_MINUTE", 10)
    # 持久记忆写入去重相似度阈值（>= 阈值视为同一事实，跳过入库）
    MEMORY_DEDUP_THRESHOLD = float(os.getenv("MEMORY_DEDUP_THRESHOLD", "0.88"))
    # 记忆抽取 LLM 请求的最大输出 tokens（用户 provider 配置的 max_tokens 优先）
    MEMORY_EXTRACT_MAX_TOKENS = _env_int("MEMORY_EXTRACT_MAX_TOKENS", 4000)
    # QA 对话历史 token 预算：从最近消息向前滑动窗口，超出预算的早期消息丢弃
    QA_HISTORY_TOKEN_BUDGET = _env_int("QA_HISTORY_TOKEN_BUDGET", 4096)
    # 持久记忆检索时间加权：每早一天衰减 0.02，5 天后不再加权（封顶 ±10%）
    MEMORY_TEMPORAL_DECAY_PER_DAY = float(os.getenv("MEMORY_TEMPORAL_DECAY_PER_DAY", "0.02"))
    # 记忆负面反馈（没用）累计达该阈值时，管理页标注"建议删除"（不自动删）
    MEMORY_FEEDBACK_SUGGEST_THRESHOLD = int(os.getenv("MEMORY_FEEDBACK_SUGGEST_THRESHOLD", "3"))
    # 本地 bge-m3（1024 维，8192 上下文）：D 盘已有模型，无需下载
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "D:/rag-medical/models/bge-m3")
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    EMBEDDING_MAX_LENGTH = int(os.getenv("EMBEDDING_MAX_LENGTH", "4096"))
    # 模型加载前要求系统剩余可用内存下限（MB）；不足则跳过加载并降级，
    # 避免模型内存占用拖垮登录等与向量无关的功能
    EMBEDDING_MIN_FREE_MEMORY_MB = int(os.getenv("EMBEDDING_MIN_FREE_MEMORY_MB", "4096"))
    # 轻量备选模型：主模型因内存不足/加载失败时回退到该模型（语义向量仍可用，
    # 维度与主模型不同时检索侧自动走 BM25，该模型仅用于语义重排等不依赖索引的场景）。
    # 服务器低配（如 2 核 2GB）可直接把 EMBEDDING_MODEL 指到这里。
    EMBEDDING_FALLBACK_MODEL = os.getenv(
        "EMBEDDING_FALLBACK_MODEL", "shibing624/text2vec-base-chinese"
    )
    # 备选模型加载前要求的最小可用内存（MB），再低则回退词袋
    EMBEDDING_FALLBACK_MIN_FREE_MEMORY_MB = int(
        os.getenv("EMBEDDING_FALLBACK_MIN_FREE_MEMORY_MB", "1500")
    )
    # BGE 系模型推荐查询指令（文档编码不加，仅查询加）
    EMBEDDING_QUERY_PREFIX = os.getenv(
        "EMBEDDING_QUERY_PREFIX", "为这个句子生成表示以用于检索相关文章："
    )
    # 硅基流动 API embedding（免费 bge-m3，与本地模型同维 1024，库无需重建）
    EMBEDDING_API_ENABLED = _env_bool("EMBEDDING_API_ENABLED", True)
    EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1")
    EMBEDDING_API_KEY = (
        os.getenv("EMBEDDING_API_KEY", "").strip()
        or os.getenv("SILICONFLOW_API_KEY", "").strip()
    )
    EMBEDDING_API_MODEL = os.getenv("EMBEDDING_API_MODEL", "BAAI/bge-m3")

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
    # 真实 cross-encoder 重排总开关：CPU 环境打分慢（分钟级），默认关闭走快速检索；
    # GPU 或高性能服务器上置 true 启用真实重排（本地 D 盘模型）
    RERANK_ENABLED = _env_bool("RERANK_ENABLED", False)
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "D:/rag-medical/models/bge-reranker-v2-m3")
    # 硅基流动 API rerank（免费 bge-reranker-v2-m3）：开启后 RERANK_ENABLED 自动生效
    RERANKER_API_ENABLED = _env_bool("RERANKER_API_ENABLED", True)
    RERANKER_API_BASE = os.getenv("RERANKER_API_BASE", "https://api.siliconflow.cn/v1")
    RERANKER_API_KEY = (
        os.getenv("RERANKER_API_KEY", "").strip()
        or os.getenv("SILICONFLOW_API_KEY", "").strip()
    )
    RERANKER_API_MODEL = os.getenv("RERANKER_API_MODEL", "BAAI/bge-reranker-v2-m3")
    # chunk 约 384 token，512 足够；过长的 max_length 在 CPU 上显著拖慢打分
    RERANKER_MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))
    # 16GB 内存机器建议半精度加载（2.2GB -> 1.1GB）
    RERANKER_HALF_PRECISION = _env_bool("RERANKER_HALF_PRECISION", True)

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
    SCAN_TASK_MAX_RETRIES = _env_int("SCAN_TASK_MAX_RETRIES", DEFAULT_SCAN_TASK_MAX_RETRIES)
    SECURITY_RATE_LIMIT_PER_MINUTE = _env_int("SECURITY_RATE_LIMIT_PER_MINUTE", DEFAULT_SECURITY_RATE_LIMIT_PER_MINUTE)

    AGENT_RUN_EXECUTOR = os.getenv("AGENT_RUN_EXECUTOR", "background").strip().lower()
    AGENT_MIN_STEP_INTERVAL_SECONDS = _env_float("AGENT_MIN_STEP_INTERVAL_SECONDS", 0.8)
    AGENT_SSE_HEARTBEAT_SECONDS = _env_int("AGENT_SSE_HEARTBEAT_SECONDS", 15)
    AGENT_SSE_POLL_SECONDS = _env_float("AGENT_SSE_POLL_SECONDS", 0.5)
    AGENT_GOAL_MAX_CHARS = 4000
    SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE = _env_int("SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE", DEFAULT_SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE)

    GITHUB_API_TIMEOUT_SECONDS = _env_int(
        "GITHUB_API_TIMEOUT_SECONDS", DEFAULT_GITHUB_API_TIMEOUT_SECONDS
    )
    GITHUB_MAX_REDIRECTS = _env_int("GITHUB_MAX_REDIRECTS", DEFAULT_GITHUB_MAX_REDIRECTS)
    SCA_OSV_ENABLED = _env_bool("SCA_OSV_ENABLED", False)
    SCA_OSV_API_URL = os.getenv("SCA_OSV_API_URL", DEFAULT_SCA_OSV_API_URL)
    SCA_REQUEST_TIMEOUT_SECONDS = _env_int(
        "SCA_REQUEST_TIMEOUT_SECONDS", DEFAULT_SCA_REQUEST_TIMEOUT_SECONDS
    )
    SCA_CACHE_TTL_SECONDS = _env_int("SCA_CACHE_TTL_SECONDS", DEFAULT_SCA_CACHE_TTL_SECONDS)
    SCA_MAX_DEPENDENCIES = _env_int("SCA_MAX_DEPENDENCIES", DEFAULT_SCA_MAX_DEPENDENCIES)

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
    def validate_security_settings(cls, settings: Mapping[str, Any] | Any | None = None) -> None:
        """Validate security-sensitive settings from Flask mappings or config objects."""
        configuration: Mapping[str, Any] | Any = settings if settings is not None else cls

        def setting(name: str, default: Any = "") -> Any:
            if isinstance(configuration, Mapping):
                return configuration.get(name, default)
            return getattr(configuration, name, default)

        def positive_int(name: str, default: int, *, maximum: int | None = None) -> int:
            try:
                value = int(setting(name, default))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a positive integer") from exc
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            if maximum is not None and value > maximum:
                raise ValueError(f"{name} must not exceed {maximum}")
            return value

        def boolean(name: str, default: bool) -> bool:
            value = setting(name, default)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
            if isinstance(value, int) and value in {0, 1}:
                return bool(value)
            raise ValueError(f"{name} must be a boolean")

        app_env = str(setting("APP_ENV", cls.APP_ENV)).strip().lower()
        if app_env not in {"development", "local", "testing", "staging", "production", "prod"}:
            raise ValueError(
                "APP_ENV must be one of development, local, testing, staging, production, prod"
            )

        origins = normalize_cors_origins(setting("CORS_ALLOWED_ORIGINS", cls.CORS_ALLOWED_ORIGINS))
        if not origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain at least one explicit origin")

        if app_env in {"production", "prod"}:
            if not cls._is_strong_secret(setting("SECRET_KEY", cls.SECRET_KEY)):
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and not use a placeholder in production"
                )
            if not cls._is_strong_secret(setting("JWT_SECRET_KEY", cls.JWT_SECRET_KEY)):
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters and not use a placeholder in production"
                )

        workspace_root = Path(str(setting("SECURITY_WORKSPACE_ROOT", cls.SECURITY_WORKSPACE_ROOT))).expanduser()
        if not workspace_root.is_absolute():
            workspace_root = BASE_DIR / workspace_root
        workspace_root = workspace_root.resolve()
        if workspace_root == Path(workspace_root.anchor):
            raise ValueError("SECURITY_WORKSPACE_ROOT must not point to a filesystem root")

        queue_name = str(setting("RQ_QUEUE_NAME", cls.RQ_QUEUE_NAME)).strip()
        if not queue_name:
            raise ValueError("RQ_QUEUE_NAME must not be empty")

        rq_async_value = setting("RQ_ASYNC", cls.RQ_ASYNC)
        rq_async = (
            rq_async_value.strip().lower() in {"1", "true", "yes", "on"}
            if isinstance(rq_async_value, str)
            else bool(rq_async_value)
        )

        positive_int(
            "SCAN_TASK_MAX_RETRIES",
            setting("SCAN_TASK_MAX_RETRIES", DEFAULT_SCAN_TASK_MAX_RETRIES),
            maximum=MAX_SCAN_TASK_MAX_RETRIES,
        )

        positive_int(
            "SECURITY_RATE_LIMIT_PER_MINUTE",
            setting("SECURITY_RATE_LIMIT_PER_MINUTE", DEFAULT_SECURITY_RATE_LIMIT_PER_MINUTE),
            maximum=10_000,
        )
        positive_int(
            "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE",
            setting("SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE", DEFAULT_SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE),
            maximum=1_000,
        )
        if rq_async:
            redis_url = str(setting("REDIS_URL", cls.REDIS_URL)).strip()
            parsed = urlparse(redis_url)
            if parsed.scheme not in {"redis", "rediss"} or not parsed.netloc:
                raise ValueError(
                    "REDIS_URL must be a redis:// or rediss:// URL when RQ_ASYNC is enabled"
                )

        upload_limit = positive_int("ARCHIVE_MAX_UPLOAD_BYTES", cls.ARCHIVE_MAX_UPLOAD_BYTES)
        extract_limit = positive_int("ARCHIVE_MAX_EXTRACT_BYTES", cls.ARCHIVE_MAX_EXTRACT_BYTES)
        positive_int("ARCHIVE_MAX_FILES", cls.ARCHIVE_MAX_FILES)
        positive_int("ARCHIVE_MAX_DEPTH", cls.ARCHIVE_MAX_DEPTH)
        if extract_limit < upload_limit:
            raise ValueError(
                "ARCHIVE_MAX_EXTRACT_BYTES must be greater than or equal to ARCHIVE_MAX_UPLOAD_BYTES"
            )

        positive_int(
            "GITHUB_API_TIMEOUT_SECONDS", cls.GITHUB_API_TIMEOUT_SECONDS, maximum=300
        )
        github_max_redirects = positive_int(
            "GITHUB_MAX_REDIRECTS", cls.GITHUB_MAX_REDIRECTS, maximum=1
        )
        if github_max_redirects != 1:
            raise ValueError("GITHUB_MAX_REDIRECTS must be exactly 1 for fixed-host archive retrieval")
        osv_api_url = str(setting("SCA_OSV_API_URL", cls.SCA_OSV_API_URL)).strip()
        parsed_osv_url = urlparse(osv_api_url)
        if (
            parsed_osv_url.scheme != "https"
            or not parsed_osv_url.netloc
            or parsed_osv_url.username
            or parsed_osv_url.password
            or parsed_osv_url.fragment
        ):
            raise ValueError("SCA_OSV_API_URL must be a credential-free HTTPS URL")
        positive_int("SCA_REQUEST_TIMEOUT_SECONDS", cls.SCA_REQUEST_TIMEOUT_SECONDS, maximum=300)
        positive_int("SCA_CACHE_TTL_SECONDS", cls.SCA_CACHE_TTL_SECONDS, maximum=31 * 24 * 60 * 60)
        positive_int(
            "SCA_MAX_DEPENDENCIES", cls.SCA_MAX_DEPENDENCIES, maximum=MAX_SCA_DEPENDENCIES
        )

        boolean("SECURITY_KNOWLEDGE_VECTOR_ENABLED", cls.SECURITY_KNOWLEDGE_VECTOR_ENABLED)
        boolean("REMEDIATION_LLM_ENABLED", cls.REMEDIATION_LLM_ENABLED)
        positive_int(
            "REMEDIATION_MAX_CONTEXT_CHARS",
            cls.REMEDIATION_MAX_CONTEXT_CHARS,
            maximum=MAX_REMEDIATION_CONTEXT_CHARS,
        )
        positive_int(
            "REMEDIATION_MAX_OUTPUT_CHARS",
            cls.REMEDIATION_MAX_OUTPUT_CHARS,
            maximum=MAX_REMEDIATION_OUTPUT_CHARS,
        )
        positive_int(
            "REMEDIATION_RETRIEVAL_TOP_K",
            cls.REMEDIATION_RETRIEVAL_TOP_K,
            maximum=MAX_REMEDIATION_RETRIEVAL_TOP_K,
        )
        positive_int(
            "REMEDIATION_PATCH_MAX_LINES",
            cls.REMEDIATION_PATCH_MAX_LINES,
            maximum=MAX_REMEDIATION_PATCH_MAX_LINES,
        )
        positive_int(
            "REMEDIATION_PATCH_MAX_CHARS",
            cls.REMEDIATION_PATCH_MAX_CHARS,
            maximum=MAX_REMEDIATION_PATCH_MAX_CHARS,
        )
