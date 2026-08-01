"""Validated remediation configuration accessors."""
from __future__ import annotations

from flask import current_app

def _config_int(name: str, default: int) -> int:
    value = current_app.config.get(name, default)
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default

def _config_bool(name: str) -> bool:
    value = current_app.config.get(name, False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
