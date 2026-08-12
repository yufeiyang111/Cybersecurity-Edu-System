# -*- coding: utf-8 -*-
"""T04 原生 Tool Calling 测试：call_id 保留、并列 delta 合并、混合文本拒绝。"""
from __future__ import annotations

import pytest

from app.services.security_agent.model.contracts import (
    AgentModelMessage,
    AgentModelRequest,
    AgentModelResponse,
    AgentModelStreamEvent,
    AgentModelToolCall,
    AgentStreamEventType,
    ContractValidationError,
)
from app.services.security_agent.model.gateway import (
    AgentModelGateway,
    merge_tool_call_arguments,
)


def test_native_tool_calls_preserve_provider_call_id():
    response = AgentModelResponse(
        content=None,
        tool_calls=(
            AgentModelToolCall(
                call_id="call_01JX",
                name="read_code_slice",
                arguments={"file_path": "app/auth.py"},
            ),
        ),
        finish_reason="tool_calls",
        provider_name="fake",
        model="fake-model",
    )
    assert response.tool_calls[0].call_id == "call_01JX"


def test_parallel_tool_call_argument_deltas_merge_by_call_id():
    deltas = [
        ("call_a", '{"file_p'),
        ("call_b", '{"symbol":'),
        ("call_a", 'ath": "a.py"}'),
        ("call_b", ' "login"}'),
    ]
    merged = merge_tool_call_arguments(deltas)
    assert merged["call_a"] == '{"file_path": "a.py"}'
    assert merged["call_b"] == '{"symbol": "login"}'
    assert set(merged) == {"call_a", "call_b"}


def test_parallel_tool_call_deltas_do_not_cross_lines():
    deltas = [
        ("call_a", '{"file_path": "a.py", "start_line": 1'),
        ("call_b", '{"query": "sql", "limit": 10'),
        ("call_a", ', "end_line": 50}'),
        ("call_b", "}"),
    ]
    merged = merge_tool_call_arguments(deltas)
    assert merged["call_a"] == '{"file_path": "a.py", "start_line": 1, "end_line": 50}'
    assert merged["call_b"] == '{"query": "sql", "limit": 10}'


def test_mixed_text_and_tool_call_rejected_as_final_answer():
    """Provider 返回文本与 Tool Call 混合时不能把未校验文本当最终回答。"""
    from app.services.security_agent.loop.actions import ActionKind

    with pytest.raises(ContractValidationError):
        AgentModelResponse(
            content="看起来完成了一半",
            tool_calls=(
                AgentModelToolCall(
                    call_id="call_1", name="read_code_slice", arguments={}
                ),
            ),
            finish_reason="stop",
            provider_name="fake",
            model="fake-model",
        )
    # 单独文本可安全转为 final_answer
    plain = AgentModelResponse(
        content="完成",
        tool_calls=(),
        finish_reason="stop",
        provider_name="fake",
        model="fake-model",
    )
    action = plain.to_action()
    assert action.kind == ActionKind.FINAL_ANSWER


def test_stream_events_sequence_order_preserved():
    events = [
        AgentModelStreamEvent(
            event_type=AgentStreamEventType.TOOL_CALL_STARTED.value,
            call_id="call_1",
            payload={"name": "read_code_slice"},
        ),
        AgentModelStreamEvent(
            event_type=AgentStreamEventType.TOOL_CALL_ARGUMENTS_DELTA.value,
            call_id="call_1",
            delta='{"file_path": "a.py"}',
        ),
        AgentModelStreamEvent(
            event_type=AgentStreamEventType.TOOL_CALL_COMPLETED.value,
            call_id="call_1",
        ),
        AgentModelStreamEvent(
            event_type=AgentStreamEventType.USAGE.value,
            payload={"total_tokens": 30},
        ),
        AgentModelStreamEvent(event_type=AgentStreamEventType.COMPLETED.value),
    ]
    gateway = AgentModelGateway()
    collected = list(gateway.normalize_stream(events))
    assert [event.event_type for event in collected] == [
        "tool_call_started",
        "tool_call_arguments_delta",
        "tool_call_completed",
        "usage",
        "completed",
    ]


def test_tool_result_roundtrip_message_for_next_turn():
    """Tool Result 用正确 tool_call_id 回填到下一次模型请求。"""
    from app.services.security_agent.model.context_renderer import (
        append_tool_results,
    )

    messages = (
        AgentModelMessage(role="user", content="检查越权"),
        AgentModelMessage(
            role="assistant",
            content=None,
            tool_calls=(
                AgentModelToolCall(
                    call_id="call_9",
                    name="get_authentication_map",
                    arguments={},
                ),
            ),
        ),
    )
    results = [
        {
            "call_id": "call_9",
            "tool_name": "get_authentication_map",
            "status": "succeeded",
            "summary": "定位 3 个入口",
            "structured": {},
            "artifact_refs": [],
            "warning_codes": [],
            "error_code": None,
        }
    ]
    next_messages = append_tool_results(messages, results)
    tool_message = next_messages[-1]
    assert tool_message.role == "tool"
    assert tool_message.tool_call_id == "call_9"
    assert "定位 3 个入口" in tool_message.content


def test_tool_result_without_call_id_rejected():
    from app.services.security_agent.model.context_renderer import (
        append_tool_results,
    )

    with pytest.raises(ValueError):
        append_tool_results(
            (),
            [
                {
                    "call_id": "",
                    "tool_name": "x",
                    "status": "succeeded",
                    "summary": "",
                }
            ],
        )
