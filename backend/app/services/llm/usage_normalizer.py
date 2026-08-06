"""Normalize provider usage payloads into a stable cache-aware shape.

Learned from LabexAgent's extractUsage: providers report prompt-cache tokens
under different field names (OpenAI/DeepSeek, Anthropic, or flat fields). This
module maps them into cached / cache_write / reported flags plus token counts.
"""
from __future__ import annotations

from typing import Any

CACHE_STATUS_DISABLED = "disabled"
CACHE_STATUS_NOT_REPORTED = "not_reported"
CACHE_STATUS_MISS = "miss"
CACHE_STATUS_WRITE_ONLY = "write_only"
CACHE_STATUS_HIT = "hit"

_CACHE_READ_KEYS: tuple[tuple[str, ...], ...] = (
    ("prompt_tokens_details", "cached_tokens"),
    ("input_token_details", "cache_read"),
    ("cache_read_input_tokens",),
    ("cached_tokens",),
)

_CACHE_WRITE_KEYS: tuple[tuple[str, ...], ...] = (
    ("input_token_details", "cache_creation"),
    ("cache_creation_input_tokens",),
    ("cache_creation", "ephemeral_5m_input_tokens"),
    ("cache_creation", "ephemeral_1h_input_tokens"),
)


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a stable usage dict or None when the payload is not usable."""
    if not isinstance(usage, dict) or not usage:
        return None
    cached = _first_positive(*[_nested_int(usage, *keys) for keys in _CACHE_READ_KEYS])
    cache_write = _first_positive(*[_nested_int(usage, *keys) for keys in _CACHE_WRITE_KEYS])
    reported = cached > 0 or cache_write > 0
    prompt = _first_positive(
        _nested_int(usage, "prompt_tokens"),
        _nested_int(usage, "input_tokens"),
        cached + cache_write,
    )
    completion = _first_positive(
        _nested_int(usage, "completion_tokens"),
        _nested_int(usage, "output_tokens"),
    )
    total = _first_positive(
        _nested_int(usage, "total_tokens"),
        prompt + completion,
    )
    if not reported and total == 0 and prompt == 0 and completion == 0:
        return None
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": cached,
        "cache_write_tokens": cache_write,
        "cache_usage_reported": reported,
    }


def cache_status(cache_usage_reported: bool, *, cached_tokens: int, cache_write_tokens: int) -> str:
    """Five-state cache telemetry status matching LabexAgent's CacheTelemetryStatus."""
    if not cache_usage_reported:
        return CACHE_STATUS_NOT_REPORTED
    if cached_tokens > 0:
        return CACHE_STATUS_HIT
    if cache_write_tokens > 0:
        return CACHE_STATUS_WRITE_ONLY
    return CACHE_STATUS_MISS


def _nested_int(usage: dict[str, Any], *path: str) -> int:
    current: Any = usage
    for part in path:
        if not isinstance(current, dict):
            return 0
        current = current.get(part)
    if isinstance(current, bool):
        return 0
    if isinstance(current, int):
        return current
    if isinstance(current, float) and current.is_integer():
        return int(current)
    if isinstance(current, str) and current.strip().isdigit():
        return int(current.strip())
    return 0


def _first_positive(*values: int) -> int:
    for value in values:
        if value > 0:
            return value
    return 0
