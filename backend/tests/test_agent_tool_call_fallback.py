# -*- coding: utf-8 -*-
"""T04 JSON Fallback 测试：严格 schema、额外字段拒绝、一次修复、未知工具拒绝。"""
from __future__ import annotations

import json

import pytest

from app.services.security_agent.model.action_parser import (
    ActionParseError,
    ACTION_SCHEMA_VERSION,
    parse_action_envelope,
    repair_prompt,
)
from app.services.security_agent.model.contracts import (
    AgentModelToolCall,
)


def test_parse_tool_calls_envelope():
    envelope = {
        "action": "tool_calls",
        "payload": {
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "read_code_slice",
                    "arguments": {"file_path": "a.py"},
                }
            ]
        },
    }
    response = parse_action_envelope(json.dumps(envelope, ensure_ascii=False))
    assert response.tool_calls == (
        AgentModelToolCall(call_id="call_1", name="read_code_slice", arguments={"file_path": "a.py"}),
    )
    assert response.content is None


def test_parse_final_answer_envelope():
    envelope = {"action": "final_answer", "payload": {"content": "完成"}}
    response = parse_action_envelope(json.dumps(envelope, ensure_ascii=False))
    assert response.content == "完成"
    assert response.tool_calls == ()


def test_parse_rejects_unknown_action():
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps({"action": "run_arbitrary_code", "payload": {}})
        )


def test_parse_rejects_unknown_tool_field():
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps(
                {
                    "action": "tool_calls",
                    "payload": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "name": "read_code_slice",
                                "arguments": {},
                                "eval_code": "danger",
                            }
                        ]
                    },
                },
                ensure_ascii=False,
            )
        )


def test_parse_rejects_missing_required_fields():
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps({"action": "tool_calls", "payload": {"tool_calls": [{"id": "x"}]}})
        )
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps({"action": "final_answer", "payload": {"content": ""}})
        )


def test_parse_rejects_invalid_json_no_eval():
    with pytest.raises(ActionParseError):
        parse_action_envelope("not json at all")
    with pytest.raises(ActionParseError):
        parse_action_envelope("None")
    with pytest.raises(ActionParseError):
        parse_action_envelope("['list', '不是对象']")


def test_parse_rejects_extra_top_level_fields():
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps(
                {
                    "action": "final_answer",
                    "payload": {"content": "完成"},
                    "hidden_reasoning": "思考全文",
                }
            )
        )


def test_repair_prompt_returns_bounded_instruction():
    prompt = repair_prompt("工具调用缺少 name 字段")
    assert "上次输出未通过校验" in prompt
    assert "name" in prompt
    assert str(ACTION_SCHEMA_VERSION) in prompt


def test_parse_rejects_tool_name_as_code_or_eval():
    """工具名必须是指定字符串，禁止把任意表达式当工具名。"""
    with pytest.raises(ActionParseError):
        parse_action_envelope(
            json.dumps(
                {
                    "action": "tool_calls",
                    "payload": {
                        "tool_calls": [
                            {"id": "c1", "name": "__import__('os')", "arguments": {}}
                        ]
                    },
                }
            )
        )
