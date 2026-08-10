"""LLM-based fact extraction for persistent user memory.

Modeled after Mem0's ADD pipeline: a provider turns one QA interaction into
durable facts (preferences, decisions, goals, context) with categories.
Extraction failures degrade silently so QA is never blocked by memory.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

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
4. 如果没有任何值得记住的信息，facts 返回空数组。
5. 实体（entities）：从事实中提取可复用的名词实体（人名、组织、技术、工具等），
   entity_type 只能是 person/org/tech/other；没有则为空数组。
6. 只输出 JSON 对象，不要输出其他内容。
格式：{{"facts": [{{"category": "preference", "content": "..."}}], "entities": [{{"name": "Web安全", "type": "tech"}}]}}

问答内容：
用户问题：{question}

助手回答：{answer}
"""


def extract_facts(provider: Any, question: str, answer: str) -> dict:
    """Ask the provider to extract durable facts and entities from one QA interaction.

    Returns ``{"facts": [...], "entities": [...]}``. Retries up to
    ``LLM_MAX_RETRIES`` times (default 2) with backoff when the provider
    reports an invalid response (e.g. free-tier models that fail structured
    JSON output intermittently). When the LLM path yields nothing, a heuristic
    fallback mines explicit preference statements from the user's question so
    memory capture still works with weak/free models.
    """
    if not answer or not answer.strip():
        return {"facts": [], "entities": []}
    # 默认最多 2 次重试；provider 自带重试数（按 LLM_MAX_RETRIES 包装）时取较大者
    max_retries = max(2, int(getattr(provider, "max_retries", 0) or 0))
    for attempt in range(max_retries + 1):
        try:
            response = provider.generate(_build_request(provider, question, answer))
        except Exception:
            response = None
        parsed = _parse_response(response)
        if parsed is not None:
            if parsed["facts"]:
                return parsed
            # LLM 判定"无可记信息"：用规则兜底补漏（只补显式偏好表达，不覆盖 LLM 判断）
            fallback = _heuristic_facts(question)
            if fallback:
                logger.info("memory.extract heuristic fallback used question_len=%d", len(question))
            return {"facts": fallback, "entities": []}
        if attempt < max_retries:
            logger.warning("memory.extract invalid response, retry %d/%d", attempt + 1, max_retries)
            time.sleep(0.5 * (attempt + 1))
    return {"facts": _heuristic_facts(question), "entities": []}


def _heuristic_facts(question: str) -> list[dict]:
    """规则兜底：从用户提问中提取明确的偏好/身份/决定表达。

    免费模型对结构化抽取不可靠时保底产出；模式匹配只覆盖显式表述，
    不猜测含义，避免噪音入库。
    """
    patterns = (
        ("preference", r"我(?:喜欢|偏好|习惯|常用|平时|经常|希望|想要)[^，。,.;;！!?？]{2,40}"),
        ("fact", r"我(?:是|是一名|是个|是一位)[^，。,.;;！!?？]{2,40}"),
        ("decision", r"我(?:决定|选择)[^，。,.;;！!?？]{2,40}"),
        ("goal", r"我(?:打算|计划|准备|要)[^，。,.;;！!?？]{2,40}"),
        ("preference", r"请记住[^，。,.;;！!?？]{2,40}"),
    )
    facts: list[dict] = []
    seen: set[str] = set()
    for category, pattern in patterns:
        for match in re.finditer(pattern, question):
            raw = match.group(0).strip("，。,.;;！!?？ ")
            content = _normalize_heuristic(raw)
            if content and content not in seen and len(content) <= 2000:
                facts.append({"category": category, "content": content})
                seen.add(content)
    return facts


def _normalize_heuristic(raw: str) -> str:
    """把第一人称表达规范为第三人称："请记住我X" -> "用户X"，"我是X" -> "用户是X"。"""
    if raw.startswith("请记住"):
        content = raw[3:]
        if content.startswith("我"):
            content = content[1:]
        return "用户" + content
    if raw.startswith("我"):
        return "用户" + raw[1:]
    return raw


def _parse_response(response: Any) -> dict | None:
    """Return {"facts": [...], "entities": [...]}, or None when invalid (retryable)."""
    if not getattr(response, "is_success", False) or not getattr(response, "text", None):
        return None
    return parse_extract_response(response.text)


def parse_extract_response(text: str) -> dict:
    """Parse facts+entities JSON from an LLM response.

    Accepts the current object shape ``{"facts": [...], "entities": [...]}``
    and the legacy bare-array shape (entities default to empty) so older
    mocks and provider outputs keep working.
    """
    payload = _load_json(text)
    if isinstance(payload, list):
        return {"facts": _normalize_facts(payload), "entities": []}
    if not isinstance(payload, dict):
        return {"facts": [], "entities": []}
    facts = _normalize_facts(payload.get("facts") if isinstance(payload.get("facts"), list) else [])
    entities = _normalize_entities(payload.get("entities") if isinstance(payload.get("entities"), list) else [])
    return {"facts": facts, "entities": entities}


def _load_json(text: str):
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}|\[.*\]", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except (TypeError, ValueError):
            return None


def _normalize_facts(payload: list) -> list[dict]:
    return [
        {
            "category": str(item.get("category") or "fact")[:32],
            "content": str(item.get("content") or "").strip()[:2000],
        }
        for item in payload
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]


def _normalize_entities(payload: list) -> list[dict]:
    allowed_types = {"person", "org", "tech", "other"}
    seen: set[str] = set()
    entities: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:128]
        if not name or name in seen:
            continue
        entity_type = str(item.get("type") or item.get("entity_type") or "other").strip()[:32]
        if entity_type not in allowed_types:
            entity_type = "other"
        seen.add(name)
        entities.append({"name": name, "type": entity_type})
    return entities


def _build_request(provider: Any, question: str, answer: str):
    from app.services.llm.contracts import LLMRequest
    from app.services.llm.provider_selector import resolve_provider_max_tokens

    return LLMRequest(
        prompt=EXTRACT_PROMPT.format(question=question, answer=answer[:4000]),
        temperature=0.2,
        max_tokens=resolve_provider_max_tokens(provider, 512),
    )


def parse_facts_json(text: str) -> list[dict]:
    """Parse a JSON array from an LLM response, tolerating markdown fences.

    Backward-compatible shim: returns only the facts part of the
    extract response (entities are ignored).
    """
    return parse_extract_response(text)["facts"]
