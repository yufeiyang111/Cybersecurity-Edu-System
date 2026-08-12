# -*- coding: utf-8 -*-
"""T01 契约测试：Event Envelope v2 与冻结的 Item/Event 类型集合。

Envelope 是纯数据契约：必填字段、版本、JSON 安全序列化、payload 类型、
reasoning_summary 事件的安全字段要求、未知事件的向前兼容。
"""
from __future__ import annotations

import json

import pytest

from app.services.security_agent.timeline.contracts import (
    AGENT_EVENT_V2_TYPES,
    EVENT_SCHEMA_VERSION_V2,
    AgentEventEnvelope,
    ItemType,
)


def test_envelope_required_fields():
    with pytest.raises(ValueError):
        AgentEventEnvelope.from_dict(
            {
                "event_id": 1,
                "run_id": 13,
                "event_type": "run.created",
            }
        )
    with pytest.raises(ValueError):
        AgentEventEnvelope.from_dict(
            {
                "event_id": 1,
                "sequence": 42,
                "event_type": "run.created",
            }
        )
    with pytest.raises(ValueError):
        AgentEventEnvelope.from_dict(
            {
                "event_id": 1,
                "sequence": 42,
                "run_id": 13,
            }
        )


def test_envelope_schema_version_defaults_to_2():
    envelope = AgentEventEnvelope.from_dict(
        {
            "event_id": 9001,
            "sequence": 42,
            "run_id": 13,
            "event_type": "run.created",
        }
    )
    assert envelope.schema_version == EVENT_SCHEMA_VERSION_V2 == 2


def test_envelope_json_roundtrip_keeps_chinese():
    envelope = AgentEventEnvelope(
        event_id=9001,
        sequence=42,
        schema_version=EVENT_SCHEMA_VERSION_V2,
        conversation_id=5,
        turn_id=8,
        run_id=13,
        iteration=4,
        item_id="toolcall_01J",
        parent_item_id="modelturn_01J",
        event_type="item.tool_call.completed",
        state_version=11,
        occurred_at="2026-08-12T10:00:00Z",
        trace_id="trace-1",
        payload={"summary": "读取 app/auth.py 第 20-80 行"},
    )
    encoded = json.dumps(envelope.to_dict(), ensure_ascii=False)
    assert "app/auth.py" in encoded
    assert "\\u" not in encoded.replace("\\u", "", 0)  # 不要求严格，仅 sanity
    restored = AgentEventEnvelope.from_dict(json.loads(encoded))
    assert restored == envelope


def test_envelope_payload_must_be_dict():
    with pytest.raises(ValueError):
        AgentEventEnvelope.from_dict(
            {
                "event_id": 1,
                "sequence": 1,
                "run_id": 1,
                "event_type": "run.created",
                "payload": ["not", "a", "dict"],
            }
        )


def test_item_types_frozen_includes_reasoning_summary():
    expected = {
        "user_message",
        "intent_summary",
        "plan",
        "decision_summary",
        "reasoning_summary",
        "tool_call",
        "tool_result",
        "observation",
        "approval",
        "assistant_message",
        "controller_feedback",
        "warning",
    }
    actual = {item.value for item in ItemType}
    assert expected <= actual


def test_event_types_frozen_v2():
    for event_type in (
        "run.created",
        "run.state.changed",
        "run.completed",
        "run.failed",
        "run.canceled",
        "item.user_message.created",
        "item.intent.completed",
        "item.plan.created",
        "item.plan.updated",
        "item.decision.created",
        "item.reasoning_summary.started",
        "item.reasoning_summary.delta",
        "item.reasoning_summary.completed",
        "item.reasoning_summary.failed",
        "item.tool_call.started",
        "item.tool_call.completed",
        "item.tool_call.failed",
        "item.tool_result.created",
        "item.observation.created",
        "item.approval.requested",
        "item.approval.resolved",
        "item.assistant_message.started",
        "item.assistant_message.delta",
        "item.assistant_message.completed",
        "item.assistant_message.failed",
        "item.controller_feedback.created",
        "budget.updated",
        "strategy.provider_switched",
        "warning.raised",
        "checkpoint.created",
        "heartbeat",
    ):
        assert event_type in AGENT_EVENT_V2_TYPES, event_type


def test_unknown_event_type_acceptable_for_forward_compat():
    """未知事件允许安全解析，不破坏水位（spec L-08）。"""
    envelope = AgentEventEnvelope.from_dict(
        {
            "event_id": 7,
            "sequence": 100,
            "run_id": 1,
            "event_type": "item.future_feature.completed",
        }
    )
    assert envelope.event_type == "item.future_feature.completed"


def test_reasoning_summary_event_requires_sensitive_level():
    with pytest.raises(ValueError):
        AgentEventEnvelope.from_dict(
            {
                "event_id": 8,
                "sequence": 101,
                "run_id": 1,
                "event_type": "item.reasoning_summary.delta",
                "payload": {"delta": "推理摘要增量"},
            }
        )
    envelope = AgentEventEnvelope.from_dict(
        {
            "event_id": 9,
            "sequence": 102,
            "run_id": 1,
            "event_type": "item.reasoning_summary.delta",
            "payload": {"delta": "推理摘要增量", "sensitive_level": "internal"},
        }
    )
    assert envelope.payload["sensitive_level"] == "internal"


def test_heartbeat_never_enters_payload_semantics():
    """heartbeat 是正式事件，不得携带业务 payload。"""
    envelope = AgentEventEnvelope.from_dict(
        {
            "event_id": 10,
            "sequence": 103,
            "run_id": 1,
            "event_type": "heartbeat",
        }
    )
    assert envelope.payload == {}
