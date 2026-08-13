# -*- coding: utf-8 -*-
"""Action Envelope 五种冻结动作解析测试（spec §4.1/C-03）。"""
from __future__ import annotations

import json

import pytest

from app.services.security_agent.model.action_parser import (
    ActionParseError,
    parse_action_envelope,
)


def test_parse_request_approval():
    response = parse_action_envelope(
        json.dumps(
            {
                "action": "request_approval",
                "payload": {
                    "request_id": "req-1",
                    "tool_name": "sensitive_tool",
                    "reason": "需要人工确认",
                },
            }
        )
    )
    assert response.action_kind == "request_approval"
    assert response.action_payload["request_id"] == "req-1"
    assert response.action_payload["tool_name"] == "sensitive_tool"
    assert response.action_payload["reason"] == "需要人工确认"


def test_parse_ask_user():
    response = parse_action_envelope(
        json.dumps({"action": "ask_user", "payload": {"question": "范围确认？"}})
    )
    assert response.action_kind == "ask_user"
    assert response.action_payload["question"] == "范围确认？"


def test_parse_plan_update():
    response = parse_action_envelope(
        json.dumps(
            {
                "action": "plan_update",
                "payload": {"patch": {"add_nodes": [{"key": "deep_scan"}]}},
            }
        )
    )
    assert response.action_kind == "plan_update"
    assert response.action_payload["patch"]["add_nodes"][0]["key"] == "deep_scan"


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "", "tool_name": "sensitive_tool", "reason": ""},
        {"request_id": "r", "tool_name": "Bad-Tool-Name!", "reason": ""},
        {"request_id": "r", "tool_name": "ok_tool", "reason": 123},
        {"request_id": "r", "tool_name": "ok_tool", "reason": "", "extra": 1},
    ],
)
def test_parse_request_approval_rejects_invalid(payload):
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps({"action": "request_approval", "payload": payload})
        )


def test_parse_rejects_unknown_action():
    with pytest.raises(ActionParseError):
        parse_action_envelope(json.dumps({"action": "run_shell", "payload": {}}))


def test_parse_rejects_extra_top_level_fields():
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps(
                {"action": "ask_user", "payload": {"question": "q"}, "hint": "x"}
            )
        )


def test_structured_action_response_cannot_mix_with_content():
    from app.services.security_agent.model.contracts import (
        AgentModelResponse,
        ContractValidationError,
    )

    with pytest.raises(ContractValidationError):
        AgentModelResponse(
            content="文本",
            tool_calls=(),
            finish_reason="stop",
            provider_name="fallback",
            action_kind="ask_user",
            action_payload={"question": "q"},
        )
