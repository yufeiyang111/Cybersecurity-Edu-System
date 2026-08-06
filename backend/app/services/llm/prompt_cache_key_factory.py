# -*- coding: utf-8 -*-
"""为 LLM 请求生成稳定的 prompt cache routing key。

参考 LabexAgent PromptCacheKeyFactory.java 实现。

对于系统提示和工具 schema 稳定的场景（如 Agent loop），
在多次请求间复用前缀缓存能显著降低 token 成本和延迟。
缓存键由输入特征的 SHA-256 前 16 字节生成，不可逆，无敏感信息泄露。
"""
from __future__ import annotations

import hashlib


def for_stable_prefix(
    *,
    base_url: str,
    model_name: str,
    system_prompt: str,
    tool_schema_json: str,
) -> str:
    """生成稳定前缀缓存键。

    用于 Agent loop 场景：系统提示和工具定义在同一轮迭代中不变，
    provider 可缓存这段前缀，只对用户消息和工具结果计费。

    参数（非空校验在调用方保证，此处空值按空字符串处理）：
        base_url: Provider 端点
        model_name: 模型名
        system_prompt: 系统提示（可为空）
        tool_schema_json: 工具 schema 的 JSON 字符串（可为空）
    """
    digest = hashlib.sha256()
    for value in (
        _norm(base_url),
        _norm(model_name),
        _norm(system_prompt),
        _norm(tool_schema_json),
    ):
        b = value.encode("utf-8")
        digest.update(str(len(b)).encode("utf-8"))
        digest.update(b":")
        digest.update(b)
        digest.update(b"\x00")
    key_bytes = digest.digest()[:16]
    return "cyber-" + "".join(f"{b:02x}" for b in key_bytes)


def _norm(value: str | None) -> str:
    return value or ""
