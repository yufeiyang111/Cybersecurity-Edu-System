# -*- coding: utf-8 -*-
"""T01 契约测试：AgentAction 判别联合、AgentModel 请求/响应/流事件、Reasoning Summary。

先于实现编写；本文件只依赖纯 Python 契约模块，不连接 Provider 或数据库。
"""
from __future__ import annotations

import json

import pytest

from app.services.security_agent.loop.actions import (
    ActionKind,
    AgentAction,
    AgentActionError,
    AskUserAction,
    FinalAnswerAction,
    PlanUpdateAction,
    RequestApprovalAction,
    ToolCallAction,
)
from app.services.security_agent.loop.policy import (
    REASONING_SUMMARY_MAX_CHARS,
    AgentLoopPolicy,
    PolicyValidationError,
)
from app.services.security_agent.model.contracts import (
    AgentModelMessage,
    AgentModelRequest,
    AgentModelResponse,
    AgentModelStreamEvent,
    AgentModelToolCall,
    AgentStreamEventType,
    AgentToolDefinition,
    ContractValidationError,
    ProviderCapabilities,
    ReasoningSummary,
)


# ---------------------------------------------------------------- actions


def test_action_roundtrip_all_kinds():
    cases = [
        AgentAction(
            kind=ActionKind.TOOL_CALLS,
            action=ToolCallAction(
                call_id="call_01J",
                name="read_code_slice",
                arguments={"file_path": "app/auth.py", "start_line": 20, "end_line": 80},
            ),
        ),
        AgentAction(
            kind=ActionKind.PLAN_UPDATE,
            action=PlanUpdateAction(
                patch={
                    "add_nodes": [
                        {"key": "auth_check", "tool_name": "get_authentication_map"}
                    ]
                }
            ),
        ),
        AgentAction(
            kind=ActionKind.REQUEST_APPROVAL,
            action=RequestApprovalAction(
                request_id="appr_1",
                tool_name="run_deep_review",
                reason="敏感读取需要审批",
            ),
        ),
        AgentAction(
            kind=ActionKind.ASK_USER,
            action=AskUserAction(question="是否继续检查水平越权？"),
        ),
        AgentAction(
            kind=ActionKind.FINAL_ANSWER,
            action=FinalAnswerAction(content="审查完成，发现 3 个高风险项。"),
        ),
    ]
    for action in cases:
        restored = AgentAction.from_dict(action.to_dict())
        assert restored.kind == action.kind
        assert restored.action == action.action


def test_action_from_dict_rejects_unknown_kind():
    with pytest.raises(AgentActionError):
        AgentAction.from_dict({"kind": "run_arbitrary_code", "action": {}})


def test_action_from_dict_rejects_mismatched_payload():
    with pytest.raises(AgentActionError):
        AgentAction.from_dict(
            {
                "kind": ActionKind.TOOL_CALLS.value,
                "action": {"content": "这不是工具调用"},
            }
        )


# ---------------------------------------------------------------- model request


def test_model_request_message_order_and_tools():
    request = AgentModelRequest(
        messages=(
            AgentModelMessage(role="system", content="安全边界"),
            AgentModelMessage(role="user", content="检查越权"),
        ),
        tools=(
            AgentToolDefinition(
                name="read_code_slice",
                description="读取受限代码切片",
                input_schema={"type": "object", "properties": {}},
            ),
        ),
        tool_choice="auto",
        temperature=0.3,
        max_tokens=1200,
    )
    assert [message.role for message in request.messages] == ["system", "user"]
    assert request.tools[0].name == "read_code_slice"
    assert request.tool_choice == "auto"


def test_model_request_metadata_carries_mode_iteration_budget_watermark():
    request = AgentModelRequest(
        messages=(AgentModelMessage(role="user", content="目标"),),
        tools=(),
        tool_choice=None,
        temperature=0.2,
        max_tokens=800,
        metadata={
            "mode": "hybrid",
            "iteration": 3,
            "budget": {"max_tool_calls": 30},
            "context_watermark": 42,
        },
    )
    assert request.metadata["mode"] == "hybrid"
    assert request.metadata["iteration"] == 3
    assert request.metadata["budget"]["max_tool_calls"] == 30
    assert request.metadata["context_watermark"] == 42


def test_model_request_validation():
    with pytest.raises(ContractValidationError):
        AgentModelRequest(
            messages=(), tools=(), tool_choice=None, temperature=0.2, max_tokens=100
        )
    with pytest.raises(ContractValidationError):
        AgentModelRequest(
            messages=(AgentModelMessage(role="admin", content="x"),),
            tools=(),
            tool_choice=None,
            temperature=0.2,
            max_tokens=100,
        )
    with pytest.raises(ContractValidationError):
        AgentModelRequest(
            messages=(AgentModelMessage(role="user", content="x"),),
            tools=(),
            tool_choice=None,
            temperature=1.5,
            max_tokens=100,
        )
    with pytest.raises(ContractValidationError):
        AgentModelRequest(
            messages=(AgentModelMessage(role="user", content="x"),),
            tools=(),
            tool_choice=None,
            temperature=0.2,
            max_tokens=0,
        )


def test_model_response_mutually_exclusive_actions():
    with pytest.raises(ContractValidationError):
        AgentModelResponse(
            content="最终回答",
            tool_calls=(
                AgentModelToolCall(
                    call_id="call_1", name="read_code_slice", arguments={}
                ),
            ),
            finish_reason=None,
            provider_name="fake",
            model="fake-model",
        )
    plain = AgentModelResponse(
        content="最终回答",
        tool_calls=(),
        finish_reason="stop",
        provider_name="fake",
        model="fake-model",
    )
    assert plain.validate() is None


def test_model_response_to_action():
    final = AgentModelResponse(
        content="审查完成",
        tool_calls=(),
        finish_reason="stop",
        provider_name="fake",
        model="fake-model",
    )
    action = final.to_action()
    assert action.kind == ActionKind.FINAL_ANSWER

    tooled = AgentModelResponse(
        content=None,
        tool_calls=(
            AgentModelToolCall(
                call_id="call_2", name="get_authentication_map", arguments={}
            ),
        ),
        finish_reason="tool_calls",
        provider_name="fake",
        model="fake-model",
    )
    action = tooled.to_action()
    assert action.kind == ActionKind.TOOL_CALLS


def test_stream_event_type_frozen_set():
    expected = {
        AgentStreamEventType.OUTPUT_TEXT_DELTA,
        AgentStreamEventType.DECISION_SUMMARY_DELTA,
        AgentStreamEventType.REASONING_SUMMARY_DELTA,
        AgentStreamEventType.TOOL_CALL_STARTED,
        AgentStreamEventType.TOOL_CALL_ARGUMENTS_DELTA,
        AgentStreamEventType.TOOL_CALL_COMPLETED,
        AgentStreamEventType.USAGE,
        AgentStreamEventType.COMPLETED,
        AgentStreamEventType.FAILED,
    }
    assert expected <= set(AgentStreamEventType)

    with pytest.raises(ContractValidationError):
        AgentModelStreamEvent(
            event_type="arbitrary_stream_event",
            item_id=None,
            call_id=None,
            delta="",
            payload={},
        )


def test_provider_capabilities_defaults():
    caps = ProviderCapabilities()
    assert caps.supports_native_tools is False
    assert caps.supports_reasoning_channel is False
    assert caps.max_context_tokens == 0


# ---------------------------------------------------------------- reasoning summary


def test_reasoning_summary_bounds():
    with pytest.raises(ContractValidationError):
        ReasoningSummary(
            source_channel="reasoning_content",
            redacted_text="x" * (REASONING_SUMMARY_MAX_CHARS + 1),
            max_chars=REASONING_SUMMARY_MAX_CHARS,
            sensitive_level="internal",
        )
    with pytest.raises(ContractValidationError):
        ReasoningSummary(
            source_channel="reasoning_content",
            redacted_text="正常摘要",
            max_chars=REASONING_SUMMARY_MAX_CHARS,
            sensitive_level="",
        )


def test_reasoning_summary_redactor_gate_rejects_secrets():
    with pytest.raises(ContractValidationError):
        ReasoningSummary(
            source_channel="reasoning_delta",
            redacted_text="包含密钥 sk-abcdefghijklmnopqrstuvw 的思考内容",
            max_chars=REASONING_SUMMARY_MAX_CHARS,
            sensitive_level="internal",
        )


def test_reasoning_summary_clean_text_passes_and_serializes():
    summary = ReasoningSummary(
        source_channel="reasoning_delta",
        redacted_text="先核对扫描证据，再按调用链定位入口。",
        max_chars=REASONING_SUMMARY_MAX_CHARS,
        sensitive_level="internal",
    )
    payload = summary.to_dict()
    assert payload["sensitive_level"] == "internal"
    assert payload["max_chars"] == REASONING_SUMMARY_MAX_CHARS
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "调用链" in encoded
    restored = ReasoningSummary.from_dict(json.loads(encoded))
    assert restored == summary


# ---------------------------------------------------------------- policy


def test_loop_policy_defaults_and_freeze():
    policy = AgentLoopPolicy()
    assert policy.run_mode == "baseline"
    assert policy.max_iterations == 20
    assert policy.max_tool_calls == 30
    assert policy.max_consecutive_model_errors == 2
    assert policy.max_same_tool_same_args == 2
    assert policy.max_plan_versions == 5
    assert policy.lease_seconds == 60
    assert policy.heartbeat_seconds == 15
    assert policy.reasoning_summary_max_chars == REASONING_SUMMARY_MAX_CHARS
    assert policy.reasoning_summary_max_chars == 6000


def test_loop_policy_roundtrip_and_validation():
    policy = AgentLoopPolicy(run_mode="hybrid", max_iterations=10)
    restored = AgentLoopPolicy.from_dict(policy.to_dict())
    assert restored.run_mode == "hybrid"
    assert restored.max_iterations == 10

    with pytest.raises(PolicyValidationError):
        AgentLoopPolicy(run_mode="autonomous_unlimited")
    with pytest.raises(PolicyValidationError):
        AgentLoopPolicy(max_iterations=0)
    with pytest.raises(PolicyValidationError):
        AgentLoopPolicy(lease_seconds=-1)
