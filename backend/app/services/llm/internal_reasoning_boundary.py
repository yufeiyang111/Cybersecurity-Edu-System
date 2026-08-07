# -*- coding: utf-8 -*-
"""统一约束 Provider 内部推理协议，避免标签进入用户可见输出。

参考 LabexAgent InternalReasoningBoundary.java 实现。

处理 MiniMax 等模型在 content 中内嵌 <think>...</think> 思考标签的情况，
以及通过独立 reasoning_content 字段传递推理内容的情况。

可见文本 = 原始 content 移除所有 thinking 标签及其内容后的纯文本。
推理内容 = reasoning_content 字段（若存在），否则丢弃。
这样处理的原因是：
  - Agent / RAG 场景下用户只需要真实回复，不需要看模型的思考过程
  - 保留 tag 内文本书写为日志字段而非用户可见文本，保持接口兼容
"""
from __future__ import annotations

import re

_THINK_BLOCK_PATTERN = re.compile(
    r"(?is)<\s*think(?:ing)?(?:\s[^>]*)?>.*?</\s*think(?:ing)?(?:\s[^>]*)?\s*>"
)
_ORPHAN_TAG_PATTERN = re.compile(
    r"(?is)<\s*/?\s*think(?:ing)?(?:\s[^>]*)?\s*/?\s*>"
)


def project(content: str, reasoning_content: str | None) -> tuple[str, str]:
    """将 LLM 返回的 content 分离为可见文本和推理文本。

    - visible = 移除所有 thinking 标签及其内容后的纯文本
    - reasoning = reasoning_content 字段（若存在且非空），否则为空字符串
    """
    visible = _strip_think_tags(content)
    reasoning = (reasoning_content.strip() if reasoning_content else "") or ""
    return visible, reasoning


def strip_visible(value: str) -> str:
    """从 content 中移除所有 thinking 标签及其内容，返回纯可见文本。"""
    return _strip_think_tags(value)


def _strip_think_tags(value: str) -> str:
    """移除所有 thinking 标签及其内容，返回纯可见文本。

    先删除完整的 <think>...</think> 块（含内容）；若仍有未闭合的
    开始标签，则丢弃其后所有内容；最后兜底删除孤立标签。
    """
    text = value or ""
    result = _THINK_BLOCK_PATTERN.sub("", text)
    open_match = _ORPHAN_TAG_PATTERN.search(result)
    if open_match is not None:
        result = result[: open_match.start()]
    else:
        result = _ORPHAN_TAG_PATTERN.sub("", result)
    return result.strip()
