"""应用 liveness/readiness 检查，不返回密钥、连接串或异常正文。"""
from __future__ import annotations

import os
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
        _chroma_component(config),
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


def _chroma_component(config: Mapping[str, Any]) -> HealthComponent:
    enabled = bool(config.get("SECURITY_KNOWLEDGE_VECTOR_ENABLED", False))
    if not enabled:
        return HealthComponent("chroma", "disabled", False)
    try:
        available = find_spec("chromadb") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    return HealthComponent("chroma", "configured_not_checked" if available else "sdk_unavailable", False)