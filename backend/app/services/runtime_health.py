"""应用 liveness/readiness 检查，不返回密钥、连接串或异常正文。"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import text

from app import db


@dataclass(frozen=True)
class HealthComponent:
    name: str
    status: str
    required: bool

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "required": self.required}


def liveness_payload() -> dict[str, Any]:
    """进程存活检查不触碰外部依赖。"""
    return {"status": "healthy", "service": "CyberGuard API"}


def readiness_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    """检查接收任务所需的本地依赖，并明确可选服务未主动联网验证。"""
    components = [
        _database_component(),
        _storage_component(config),
        _optional_component("neo4j", bool(str(config.get("NEO4J_URI", "")).strip())),
        _vector_component(config),
    ]
    required_failures = [item for item in components if item.required and item.status != "healthy"]
    return {
        "status": "ready" if not required_failures else "not_ready",
        "service": "CyberGuard API",
        "components": {item.name: item.to_dict() for item in components},
    }


def _database_component() -> HealthComponent:
    try:
        db.session.execute(text("SELECT 1"))
        return HealthComponent("database", "healthy", True)
    except Exception:
        db.session.rollback()
        return HealthComponent("database", "unavailable", True)


def _storage_component(config: Mapping[str, Any]) -> HealthComponent:
    path = Path(str(config.get("SECURITY_WORKSPACE_ROOT", ""))).expanduser()
    try:
        healthy = path.is_dir() and os.access(path, os.R_OK | os.W_OK)
    except OSError:
        healthy = False
    return HealthComponent("workspace_storage", "healthy" if healthy else "unavailable", True)


def _optional_component(name: str, configured: bool) -> HealthComponent:
    return HealthComponent(name, "configured_not_checked" if configured else "disabled", False)


def _vector_component(config: Mapping[str, Any]) -> HealthComponent:
    enabled = bool(config.get("SECURITY_KNOWLEDGE_VECTOR_ENABLED", False))
    backend = str(config.get("VECTOR_BACKEND", "qdrant")).strip().lower() or "qdrant"
    if backend not in ("chroma", "qdrant"):
        backend = "qdrant"
    if not enabled:
        return HealthComponent(backend, "disabled", False)
    try:
        healthy = _ping_vector_backend(backend, config)
    except Exception:
        healthy = False
    return HealthComponent(backend, "healthy" if healthy else "unavailable", False)


def _ping_vector_backend(backend: str, config: Mapping[str, Any]) -> bool:
    """真实连通探测；任何异常都视为不可用，不向上泄漏错误细节。"""
    if backend == "qdrant":
        return _ping_qdrant(config)
    return _ping_chroma(config)


def _ensure_no_proxy_for_loopback(url: str) -> None:
    """本地向量服务经系统代理访问会失败（本机代理对回环请求返回 502）。"""
    try:
        host = urllib.parse.urlparse(url).netloc.split(":")[0]
    except ValueError:
        host = ""
    if host in ("127.0.0.1", "localhost", "::1"):
        existing = os.environ.get("NO_PROXY", "") or os.environ.get("no_proxy", "") or ""
        hosts = {item.strip() for item in existing.split(",") if item.strip()}
        hosts.update({"127.0.0.1", "localhost"})
        os.environ["NO_PROXY"] = ",".join(sorted(hosts))
        os.environ["no_proxy"] = os.environ["NO_PROXY"]


def _ping_qdrant(config: Mapping[str, Any]) -> bool:
    url = str(config.get("QDRANT_URL", "") or "").rstrip("/") or "http://127.0.0.1:6333"
    _ensure_no_proxy_for_loopback(url)
    try:
        with urllib.request.urlopen(f"{url}/healthz", timeout=2.0) as response:
            return response.status == 200
    except Exception:
        return False


def _ping_chroma(config: Mapping[str, Any]) -> bool:
    host = str(config.get("CHROMA_HOST", "") or "").strip()
    try:
        if host:
            from chromadb.config import Settings

            client = _chroma_client(host, int(config.get("CHROMA_PORT", 8000) or 8000))
            return bool(client.heartbeat())
        path = Path(str(config.get("CHROMA_PERSIST_DIRECTORY", "chroma_db"))).expanduser()
        return path.is_dir() and os.access(path, os.R_OK | os.W_OK)
    except Exception:
        return False


def _chroma_client(host: str, port: int):
    from chromadb.config import Settings

    try:
        import chromadb

        return chromadb.Client(
            Settings(
                chroma_server_host=host,
                chroma_server_http_port=port,
                anonymized_telemetry=False,
            )
        )
    except (TypeError, ValueError):
        from chromadb import HttpClient

        return HttpClient(host=host, port=port)