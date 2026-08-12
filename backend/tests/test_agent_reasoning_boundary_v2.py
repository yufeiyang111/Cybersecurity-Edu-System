# -*- coding: utf-8 -*-
"""T01 契约测试：Reasoning 边界（v1.1 决策）。

- 完整原始思维链全文（raw chain-of-thought）不得成为可持久化字段；
- Reasoning Summary 是唯一受控摘要协议：脱敏、限长、sensitive_level；
- 持久化 Serializer 遇到原始推理字段必须丢弃并记录安全告警码。
"""
from __future__ import annotations

import json

import pytest

from app.services.security_agent.loop.policy import REASONING_SUMMARY_MAX_CHARS
from app.services.security_agent.model.contracts import (
    ContractValidationError,
    ReasoningSummary,
)
from app.services.security_agent.timeline.contracts import (
    AGENT_REASONING_RAW_REJECTED,
    sanitize_persistable_payload,
)

_RAW_FULL_COT = (
    "让我一步步思考。首先读取 auth.py，看到 login 函数……"
    "然后检查 token 校验逻辑，发现没有过期校验，这是一个越权漏洞。"
    "最后确认影响范围是全部用户会话。"
)


def test_raw_reasoning_fields_dropped_with_warning():
    payload = {
        "event_type": "item.assistant_message.delta",
        "content": "分析中",
        "raw_reasoning": _RAW_FULL_COT,
    }
    cleaned, warning_code = sanitize_persistable_payload(payload)
    assert "raw_reasoning" not in cleaned
    assert _RAW_FULL_COT not in json.dumps(cleaned, ensure_ascii=False)
    assert warning_code == AGENT_REASONING_RAW_REJECTED


def test_chain_of_thought_field_dropped_with_warning():
    payload = {"chain_of_thought": _RAW_FULL_COT, "delta": "可见文本"}
    cleaned, warning_code = sanitize_persistable_payload(payload)
    assert "chain_of_thought" not in cleaned
    assert warning_code == AGENT_REASONING_RAW_REJECTED


def test_reasoning_field_with_secret_redacted_and_warned():
    payload = {"reasoning": "思考中调用了 sk-abcdefghijklmnopqrstuvw 这个密钥"}
    cleaned, warning_code = sanitize_persistable_payload(payload)
    assert "sk-abcdefghijklmnopqrstuvw" not in json.dumps(cleaned, ensure_ascii=False)
    assert warning_code == AGENT_REASONING_RAW_REJECTED


def test_clean_reasoning_passthrough_without_warning():
    payload = {"reasoning": "先核对扫描证据，再按调用链定位入口。"}
    cleaned, warning_code = sanitize_persistable_payload(payload)
    assert cleaned["reasoning"] == "先核对扫描证据，再按调用链定位入口。"
    assert warning_code is None


def test_full_cot_never_persistable_via_nested_payload():
    payload = {
        "item_type": "assistant_message",
        "nested": {"reasoning_full": _RAW_FULL_COT, "ok": 1},
    }
    cleaned, warning_code = sanitize_persistable_payload(payload)
    serialized = json.dumps(cleaned, ensure_ascii=False)
    assert _RAW_FULL_COT not in serialized
    assert warning_code == AGENT_REASONING_RAW_REJECTED


def test_reasoning_summary_persistable_contract():
    summary = ReasoningSummary(
        source_channel="reasoning_delta",
        redacted_text="先核对扫描证据。",
        max_chars=REASONING_SUMMARY_MAX_CHARS,
        sensitive_level="internal",
    )
    payload = summary.to_dict()
    assert payload["sensitive_level"] == "internal"
    assert len(payload["redacted_text"]) <= payload["max_chars"]
    json.dumps(payload, ensure_ascii=False)  # 必须可 JSON 序列化
    restored = ReasoningSummary.from_dict(payload)
    assert restored == summary


def test_reasoning_summary_rejects_raw_full_text_semantics():
    """摘要语义不得承载完整思维链：超限即拒绝。"""
    oversized_full_cot = _RAW_FULL_COT * 100  # 超过 REASONING_SUMMARY_MAX_CHARS
    with pytest.raises(ContractValidationError):
        ReasoningSummary(
            source_channel="reasoning_content",
            redacted_text=oversized_full_cot,
            max_chars=REASONING_SUMMARY_MAX_CHARS,
            sensitive_level="internal",
        )
