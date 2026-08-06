# -*- coding: utf-8 -*-
"""Intent parsing: rule-based extraction of the audit focus from the user goal.

This is intentionally lightweight: A3 planners receive the raw goal plus these
hints. It is never treated as model output and never replaces the LLM planner.
"""
from __future__ import annotations

import re

_FOCUS_PATTERNS = (
    (("auth", "authentication"), ("鉴权", "登录", "认证", "auth", "登录态", "token 校验")),
    (("authorization", "multi_tenant"), ("越权", "授权", "多租户", "租户隔离", "权限", "rbac")),
    (("upload", "file_upload"), ("上传", "文件上传", "上传漏洞")),
    (("ssrf",), ("ssrf", "服务端请求伪造", "内网请求")),
    (("injection", "sql_injection"), ("注入", "sql 注入", "xss", "命令注入")),
    (("secrets", "secret_leak"), ("密钥", "secret", "api key", "硬编码")),
    (("dependency", "sca"), ("依赖", "第三方库", "供应链", "cve")),
    (("data_leak", "sensitive_data"), ("敏感数据", "泄露", "日志泄露", "数据脱敏")),
    (("path_traversal",), ("路径穿越", "目录穿越", "任意文件")),
    (("crypto",), ("加密", "算法", "证书")),
    (("config", "misconfiguration"), ("配置", "默认口令", "弱口令", "错误配置")),
)

_FOCUS_KEYWORDS: dict[str, tuple[str, ...]] = {
    label: tuple(keywords)
    for labels, keywords in _FOCUS_PATTERNS
    for label in labels
}


def parse_intent(goal_text: str) -> dict:
    """Extract structured focus hints from the goal text (pure, deterministic)."""
    lowered = (goal_text or "").lower()
    focus_labels: list[str] = []
    for label, keywords in _FOCUS_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            focus_labels.append(label)
    return {
        "focus_labels": focus_labels[:10],
        "has_scope_constraint": bool(re.search(r"只(看|检查|关注)|仅(看|检查|关注)|重点(看|检查|关注)", lowered)),
    }
