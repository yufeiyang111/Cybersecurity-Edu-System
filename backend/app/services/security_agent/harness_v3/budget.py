# -*- coding: utf-8 -*-
"""Harness V3 的预算默认与上下文预算解析。

本模块只决定 V3 的安全默认值，不修改用户已显式提交的预算。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_DEEP_AUDIT_TOTAL_TOKENS = 16000
DEFAULT_DEEP_REVIEW_CONTEXT_CHARS = 12000
MIN_DEEP_REVIEW_CONTEXT_CHARS = 1000
MAX_DEEP_REVIEW_CONTEXT_CHARS = 20000


def apply_v3_default_budget(
    *,
    mode: str,
    budget: Mapping[str, Any] | None,
    feature_flags: Mapping[str, Any] | object,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """仅在 V3 Deep Audit 未传总 token 预算时填充安全默认值。"""
    resolved = dict(budget or {})
    if (
        str(mode or "").strip().lower() != "deep_audit"
        or not _flag_enabled(feature_flags, "harness_v3")
        or "max_total_tokens" in resolved
    ):
        return resolved

    resolved["max_total_tokens"] = _bounded_int(
        _lookup(config, "AGENT_HARNESS_V3_DEEP_AUDIT_DEFAULT_TOKENS"),
        default=DEFAULT_DEEP_AUDIT_TOTAL_TOKENS,
        minimum=1000,
        maximum=200000,
    )
    return resolved


def resolve_v3_context_char_budget(
    *,
    explicit_chars: int | None,
    config: Mapping[str, Any] | None = None,
) -> int:
    """解析单次 V3 Deep Review Context 上限，显式值始终优先。"""
    value = (
        explicit_chars
        if explicit_chars is not None
        else _lookup(config, "AGENT_HARNESS_V3_DEEP_REVIEW_CONTEXT_CHARS")
    )
    return _bounded_int(
        value,
        default=DEFAULT_DEEP_REVIEW_CONTEXT_CHARS,
        minimum=MIN_DEEP_REVIEW_CONTEXT_CHARS,
        maximum=MAX_DEEP_REVIEW_CONTEXT_CHARS,
    )


def deep_review_token_reserve(config: Mapping[str, Any] | None = None) -> int:
    """返回 V3 预留给 Deep Review / Critic 的最小 token 额度。"""
    return _bounded_int(
        _lookup(config, "AGENT_HARNESS_V3_DEEP_REVIEW_TOKEN_RESERVE"),
        default=6000,
        minimum=500,
        maximum=100000,
    )


def _flag_enabled(feature_flags: Mapping[str, Any] | object, key: str) -> bool:
    if isinstance(feature_flags, Mapping):
        return bool(feature_flags.get(key, False))
    return bool(getattr(feature_flags, key, False))


def _lookup(config: Mapping[str, Any] | None, key: str) -> Any:
    if config is None:
        return None
    return config.get(key)


def _bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ValueError("Harness V3 预算必须是整数")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Harness V3 预算必须是整数") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"Harness V3 预算必须在 {minimum} 至 {maximum} 之间")
    return parsed
