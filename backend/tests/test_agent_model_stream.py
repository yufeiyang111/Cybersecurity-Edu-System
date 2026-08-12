# -*- coding: utf-8 -*-
"""T04 流式与安全日志测试：流事件顺序、usage/finish reason、错误码映射、无泄露。"""
from __future__ import annotations

import logging

import pytest

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.llm.contracts import LLMResponse
from app.services.security_agent.model.contracts import (
    AgentModelMessage,
    AgentModelRequest,
    AgentModelResponse,
    AgentModelStreamEvent,
    AgentModelToolCall,
    AgentStreamEventType,
    ProviderCapabilities,
)
from app.services.security_agent.model.gateway import AgentModelGateway

_RAW_SECRET = "sk-abcdefghijklmnopqrstuvwxyz123456"
_RAW_PROMPT = "内部 prompt 原文，含源码片段"


class _StreamingFakeProvider:
    provider_name = "fake-stream"
    model = "fake-stream-model"
    model_version = "1"
    provider_config_id = None

    def __init__(self, events=None, warning_code=None, text=None):
        self.events = events or []
        self.warning_code = warning_code
        self.text = text

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True, supports_streaming=True)

    def generate_agent_stream(self, request):
        return iter(self.events)

    def generate_agent(self, request):
        return AgentModelResponse(
            content=self.text,
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
            warning_code=self.warning_code,
        )

    def generate(self, request):
        return LLMResponse(
            text=self.text,
            provider_name=self.provider_name,
            model=self.model,
            warning_code=self.warning_code,
        )


def _request() -> AgentModelRequest:
    return AgentModelRequest(
        messages=(AgentModelMessage(role="user", content="目标"),),
        tools=(),
        tool_choice=None,
        temperature=0.2,
        max_tokens=500,
    )


def _run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="流测试",
        mode="baseline",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_stream_events_passthrough_with_usage_and_completion(app):
    with app.app_context():
        provider = _StreamingFakeProvider(
            events=[
                AgentModelStreamEvent(
                    event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                    item_id="asst-1",
                    delta="最终回答第一段",
                ),
                AgentModelStreamEvent(
                    event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                    item_id="asst-1",
                    delta="，第二段",
                ),
                AgentModelStreamEvent(
                    event_type=AgentStreamEventType.USAGE.value,
                    payload={"prompt_tokens": 8, "completion_tokens": 6, "total_tokens": 14},
                ),
                AgentModelStreamEvent(event_type=AgentStreamEventType.COMPLETED.value),
            ]
        )
        collected = list(
            AgentModelGateway().stream_turn(
                _request(), provider=provider, run=_run(), trace_id="t-stream"
            )
        )
        types = [event.event_type for event in collected]
        assert types == ["output_text_delta", "output_text_delta", "usage", "completed"]
        usage_event = collected[2]
        assert usage_event.payload["total_tokens"] == 14
        assert collected[-1].event_type == "completed"


def test_provider_warning_code_mapped_to_response(app):
    with app.app_context():
        provider = _StreamingFakeProvider(warning_code="LLM_PROVIDER_RATE_LIMITED")
        result = AgentModelGateway().next_turn(
            _request(), provider=provider, run=_run(), trace_id="t-429"
        )
        assert result.warning_code == "LLM_PROVIDER_RATE_LIMITED"
        assert result.content is None


def test_no_raw_secrets_in_events_or_logs(app, caplog):
    with app.app_context():
        run = _run()
        provider = _StreamingFakeProvider(
            events=[
                AgentModelStreamEvent(
                    event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                    delta=f"包含 {_RAW_SECRET} 的输出",
                ),
                AgentModelStreamEvent(
                    event_type=AgentStreamEventType.REASONING_SUMMARY_DELTA.value,
                    delta="推理摘要",
                    payload={"sensitive_level": "internal"},
                ),
                AgentModelStreamEvent(event_type=AgentStreamEventType.COMPLETED.value),
            ]
        )
        with caplog.at_level(logging.WARNING, logger="app.services.security_agent"):
            list(
                AgentModelGateway().stream_turn(
                    _request(), provider=provider, run=run, trace_id="t-secret"
                )
            )
        events = AgentEvent.query.filter_by(run_id=run.id).all()
        serialized = repr([event.to_dict() for event in events])
        assert _RAW_SECRET not in serialized
        assert "prompt 原文" not in serialized
        combined_logs = "\n".join(record.getMessage() for record in caplog.records)
        assert _RAW_SECRET not in combined_logs


def test_gateway_never_logs_authorization_or_raw_body(app, caplog):
    with app.app_context():
        provider = _StreamingFakeProvider(warning_code="LLM_PROVIDER_NON_SUCCESS")
        with caplog.at_level(logging.DEBUG, logger="app.services.security_agent"):
            AgentModelGateway().next_turn(
                _request(), provider=provider, run=_run(), trace_id="t-noauth"
            )
        combined_logs = "\n".join(record.getMessage() for record in caplog.records)
        assert "Bearer " not in combined_logs
        assert "Authorization" not in combined_logs
