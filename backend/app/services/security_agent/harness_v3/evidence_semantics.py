# -*- coding: utf-8 -*-
"""Harness V3 控制类证据的固定三态语义。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping


CONTROL_EVIDENCE_KEYS = frozenset(
    {
        "authorization_guard",
        "parameterization_or_absence",
        "guard_or_absence",
        "allowlist_or_absence",
        "production_guard_or_absence",
    }
)
CONTROL_STATUS_VALUES = frozenset({"present", "absent", "unknown"})


def control_evidence_keys(required_evidence: Iterable[object]) -> tuple[str, ...]:
    """按原始顺序提取当前假设中需要判断控制状态的证据条件。"""
    keys: list[str] = []
    for raw_value in required_evidence:
        value = str(raw_value or "").strip()
        if value in CONTROL_EVIDENCE_KEYS and value not in keys:
            keys.append(value)
    return tuple(keys)


def normalize_control_assessments(
    raw_value: object,
    *,
    required_evidence: Iterable[object],
) -> dict[str, str]:
    """限制 Provider 只能为当前控制类条件声明固定三态。"""
    if raw_value is None:
        return {}
    if not isinstance(raw_value, Mapping):
        raise ValueError("detail.control_assessments 必须是对象")

    allowed = set(control_evidence_keys(required_evidence))
    normalized: dict[str, str] = {}
    for raw_key, raw_status in raw_value.items():
        key = str(raw_key or "").strip()
        if key not in allowed:
            raise ValueError("detail.control_assessments 包含未授权控制证据条件")
        if not isinstance(raw_status, str):
            raise ValueError("detail.control_assessments 的控制状态必须是字符串")
        status = raw_status.strip().lower()
        if status not in CONTROL_STATUS_VALUES:
            raise ValueError("detail.control_assessments 的控制状态只能是 present、absent 或 unknown")
        normalized[key] = status
    return normalized