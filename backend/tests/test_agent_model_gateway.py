# -*- coding: utf-8 -*-
"""T04 模型网关测试：原生 Tool Calling 与 JSON Fallback 分发、failover、调用记录。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.model.contracts import (
    AgentModelMessage,
    AgentModelRequest,
    AgentModelResponse,
    AgentModelToolCall,
    AgentToolDefinition,
    ProviderCapabilities,
)
from app.services.security_agent.model.gateway import AgentModelGateway


@pytest.fixture(autouse=True)
def _enable_v2_event_schema(app):
    """failover 事件断言使用 v2 事件名：显式开启 Event v2 flag（S-03）。"""
    app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
    yield


class _FakeNativeProvider:
    """声明原生 Tool Calling 能力的 Fake Provider，记录收到的请求。"""

    provider_name = "fake-native"
    model = "fake-native-model"
    model_version = "1"
    provider_config_id = None

    def __init__(
        self,
        response: AgentModelResponse | None = None,
        *,
        provider_name: str | None = None,
    ) -> None:
        self.response = response
        self.requests = []
        if provider_name:
            self.provider_name = provider_name

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_native_tools=True,
            supports_streaming=True,
            supports_parallel_tool_calls=True,
        )

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        return self.response


class _FakeTextProvider:
    """只有文本 generate 的 Fake Provider（走 JSON Fallback）。"""

    provider_name = "fake-text"
    model = "fake-text-model"
    model_version = "1"
    provider_config_id = None

    def __init__(self, text: str | None = None, warning_code: str | None = None) -> None:
        self.text = text
        self.warning_code = warning_code
        self.requests = []

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=False)

    def generate(self, request):
        from app.services.llm.contracts import LLMResponse

        self.requests.append(request)
        return LLMResponse(
            text=self.text,
            provider_name=self.provider_name,
            model=self.model,
            warning_code=self.warning_code,
        )


def _run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="网关测试",
        mode="hybrid",
    )
    db.session.add(run)
    db.session.flush()
    return run


def _request() -> AgentModelRequest:
    return AgentModelRequest(
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
        temperature=0.2,
        max_tokens=800,
    )


def test_gateway_native_path_passes_messages_tools_tool_choice(app):
    with app.app_context():
        provider = _FakeNativeProvider(
            AgentModelResponse(
                content=None,
                tool_calls=(
                    AgentModelToolCall(
                        call_id="call_abc",
                        name="read_code_slice",
                        arguments={"file_path": "app/auth.py"},
                    ),
                ),
                finish_reason="tool_calls",
                provider_name="fake-native",
                model="fake-native-model",
            )
        )
        request = _request()
        result = AgentModelGateway().next_turn(
            request,
            provider=provider,
            run=_run(),
            trace_id="t-native",
        )
        assert provider.requests[0].messages == request.messages
        assert provider.requests[0].tools == request.tools
        assert provider.requests[0].tool_choice == "auto"
        assert result.tool_calls[0].call_id == "call_abc"
        assert result.tool_calls[0].name == "read_code_slice"
        assert result.tool_calls[0].arguments["file_path"] == "app/auth.py"


def test_gateway_fallback_path_for_text_only_provider(app):
    with app.app_context():
        provider = _FakeTextProvider(
            text='{"action": "tool_calls", "payload": {"tool_calls": '
            '[{"id": "call_1", "name": "get_authentication_map", "arguments": {"limit": 10}}]}}'
        )
        result = AgentModelGateway().next_turn(
            _request(),
            provider=provider,
            run=_run(),
            trace_id="t-fallback",
        )
        assert result.tool_calls[0].call_id == "call_1"
        assert result.tool_calls[0].name == "get_authentication_map"
        assert result.tool_calls[0].arguments["limit"] == 10


def test_gateway_fallback_final_answer(app):
    with app.app_context():
        provider = _FakeTextProvider(
            text='{"action": "final_answer", "payload": {"content": "审查完成，发现 3 个高风险项。"}}'
        )
        result = AgentModelGateway().next_turn(
            _request(),
            provider=provider,
            run=_run(),
            trace_id="t-final",
        )
        assert result.content == "审查完成，发现 3 个高风险项。"
        assert result.tool_calls == ()


def test_gateway_failover_switches_to_second_candidate(app):
    with app.app_context():
        broken = _FakeNativeProvider(
            AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason=None,
                provider_name="fake-native",
                model="fake-native-model",
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
            )
        )
        healthy = _FakeNativeProvider(
            AgentModelResponse(
                content="备用完成",
                tool_calls=(),
                finish_reason="stop",
                provider_name="fake-native-2",
                model="fake-native-2-model",
            )
        )
        result = AgentModelGateway().next_turn(
            _request(),
            provider=broken,
            candidates=(broken, healthy),
            run=_run(),
            trace_id="t-failover",
        )
        assert result.provider_name == "fake-native-2"
        assert result.content == "备用完成"


def test_gateway_failover_emits_provider_switched_event(app):
    with app.app_context():
        from app.models.agent_events import AgentEvent

        broken = _FakeNativeProvider(
            AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason=None,
                provider_name="fake-native",
                model="fake-native-model",
                warning_code="LLM_PROVIDER_TIMEOUT",
            )
        )
        healthy = _FakeNativeProvider(
            AgentModelResponse(
                content="ok",
                tool_calls=(),
                finish_reason="stop",
                provider_name="fake-native-2",
                model="fake-native-2-model",
            ),
            provider_name="fake-native-2",
        )
        run = _run()
        AgentModelGateway().next_turn(
            _request(),
            provider=broken,
            candidates=(broken, healthy),
            run=run,
            trace_id="t-switch",
        )
        switched = (
            AgentEvent.query.filter_by(
                run_id=run.id, event_type="strategy.provider_switched"
            ).first()
        )
        assert switched is not None
        assert switched.payload_json["from_provider"] == "fake-native"
        assert switched.payload_json["to_provider"] == "fake-native-2"


def test_gateway_records_invocation(app):
    with app.app_context():
        from app.models.agent_llm import LLMInvocation

        run = _run()
        provider = _FakeNativeProvider(
            AgentModelResponse(
                content="记录我",
                tool_calls=(),
                finish_reason="stop",
                provider_name="fake-native",
                model="fake-native-model",
                usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            )
        )
        AgentModelGateway().next_turn(
            _request(), provider=provider, run=run, trace_id="t-record"
        )
        invocation = LLMInvocation.query.filter_by(run_id=run.id).one()
        assert invocation.provider_name == "fake-native"
        assert invocation.input_tokens == 10
        assert invocation.output_tokens == 4
