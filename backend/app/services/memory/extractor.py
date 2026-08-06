"""LLM-based fact extraction for persistent user memory.

Modeled after Mem0's ADD pipeline: a provider turns one QA interaction into
durable facts (preferences, decisions, goals, context) with categories.
Extraction failures degrade silently so QA is never blocked by memory.
"""
from __future__ import annotations

import json
import re
from typing import Any

EXTRACT_PROMPT = """你是记忆提取助手。从下面的一轮网络安全问答中，提取值得长期记住的关于用户的事实。

提取范围（仅限这些类别）：
- preference: 用户表达的偏好、习惯（如回答风格、关注领域）
- fact: 用户透露的稳定事实（如职业、学习目标、使用场景）
- decision: 用户做出的决定或选择
- goal: 用户的目标或计划
- other: 其他值得记住的信息

规则：
1. 只提取稳定的、未来可能有用的信息；不要提取一次性问题或技术答案本身。
2. 不要提取密码、密钥、Token、手机号、地址等敏感信息。
3. 每条事实用第三人称客观描述，如"用户是安全工程师，关注 Web 安全"。
4. 如果没有任何值得记住的信息，返回空数组。
5. 只输出 JSON 数组，不要输出其他内容。格式：[{{"category": "preference", "content": "..."}}]

问答内容：
用户问题：{question}

助手回答：{answer}
"""


def extract_facts(provider: Any, question: str, answer: str) -> list[dict]:
    """Ask the provider to extract durable facts from one QA interaction."""
    if not answer or not answer.strip():
        return []
    try:
        response = provider.generate(
            _build_request(question, answer)
        )
    except Exception:
        return []
    if not getattr(response, "is_success", False) or not getattr(response, "text", None):
        return []
    return parse_facts_json(response.text)


def _build_request(question: str, answer: str):
    from app.services.llm.contracts import LLMRequest

    return LLMRequest(
        prompt=EXTRACT_PROMPT.format(question=question, answer=answer[:4000]),
        temperature=0.2,
        max_tokens=512,
    )


def parse_facts_json(text: str) -> list[dict]:
    """Parse a JSON array from an LLM response, tolerating markdown fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError):
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except (TypeError, ValueError):
            return []
    if not isinstance(payload, list):
        return []
    return [
        {
            "category": str(item.get("category") or "fact")[:32],
            "content": str(item.get("content") or "").strip()[:2000],
        }
        for item in payload
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
