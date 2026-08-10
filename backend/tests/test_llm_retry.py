# -*- coding: utf-8 -*-
"""LLM 自动重试测试：429/5xx/超时 指数退避重试"""
import time

import pytest

from app.services.llm.contracts import LLMRequest
from app.services.llm.openai_compatible import OpenAICompatibleProvider, _should_retry_status


class FakeResponse:
    def __init__(self, status_code=200, text="{}"):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= len(self.responses):
            response = self.responses[self.calls - 1]
            if isinstance(response, Exception):
                raise response
            return response
        return FakeResponse()


@pytest.fixture
def provider():
    return OpenAICompatibleProvider(
        provider_name="fake",
        base_url="http://fake.local/v1",
        api_key="k",
        model="m",
    )


def test_should_retry_status():
    assert _should_retry_status(429)
    assert _should_retry_status(500)
    assert _should_retry_status(503)
    assert not _should_retry_status(200)
    assert not _should_retry_status(400)
    assert not _should_retry_status(404)


def test_generate_retries_on_5xx_then_succeeds(monkeypatch, provider):
    session = FakeSession([FakeResponse(500), FakeResponse(200, '{"choices":[{"message":{"content":"ok"}}]}')])
    monkeypatch.setattr(provider, "_http_client", session)
    monkeypatch.setattr("app.services.llm.openai_compatible._retry_delay", lambda attempt: 0)
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 2)

    result = provider.generate(LLMRequest(prompt="hi", max_tokens=16))

    assert session.calls == 2
    assert result.text == "ok"


def test_provider_max_tokens_caps_requests(monkeypatch):
    from app.services.llm.openai_compatible import OpenAICompatibleProvider

    recorded = {}

    class RecordingSession:
        def post(self, *args, **kwargs):
            recorded["body"] = kwargs["json"]
            return FakeResponse(200, '{"choices":[{"message":{"content":"ok"}}]}')

    provider = OpenAICompatibleProvider(
        provider_name="fake",
        base_url="http://fake.local/v1",
        api_key="k",
        model="m",
        max_tokens=4096,
    )
    monkeypatch.setattr(provider, "_http_client", RecordingSession())
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 0)

    # 用户配置的上限封顶显式的大请求
    provider.generate(LLMRequest(prompt="hi", max_tokens=16384))
    assert recorded["body"]["max_tokens"] == 4096

    # 探测类小请求不受大值影响
    provider.generate(LLMRequest(prompt="hi", max_tokens=512))
    assert recorded["body"]["max_tokens"] == 512


def test_provider_without_max_tokens_keeps_request_value(monkeypatch):
    from app.services.llm.openai_compatible import OpenAICompatibleProvider

    recorded = {}

    class RecordingSession:
        def post(self, *args, **kwargs):
            recorded["body"] = kwargs["json"]
            return FakeResponse(200, '{"choices":[{"message":{"content":"ok"}}]}')

    provider = OpenAICompatibleProvider(
        provider_name="fake",
        base_url="http://fake.local/v1",
        api_key="k",
        model="m",
        max_tokens=None,
    )
    monkeypatch.setattr(provider, "_http_client", RecordingSession())
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 0)

    provider.generate(LLMRequest(prompt="hi"))
    assert recorded["body"]["max_tokens"] == 8192


def test_generate_retries_on_timeout_then_succeeds(monkeypatch, provider):
    import requests

    session = FakeSession([
        requests.Timeout("read timed out"),
        FakeResponse(200, '{"choices":[{"message":{"content":"ok"}}]}'),
    ])
    monkeypatch.setattr(provider, "_http_client", session)
    monkeypatch.setattr("app.services.llm.openai_compatible._retry_delay", lambda attempt: 0)
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 2)

    result = provider.generate(LLMRequest(prompt="hi", max_tokens=16))

    assert session.calls == 2
    assert result.text == "ok"


def test_generate_gives_up_after_retries(monkeypatch, provider):
    session = FakeSession([FakeResponse(503), FakeResponse(503), FakeResponse(503)])
    monkeypatch.setattr(provider, "_http_client", session)
    monkeypatch.setattr("app.services.llm.openai_compatible._retry_delay", lambda attempt: 0)
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 2)

    result = provider.generate(LLMRequest(prompt="hi", max_tokens=16))

    assert session.calls == 3
    assert result.warning_code == "LLM_PROVIDER_NON_SUCCESS"


def test_generate_does_not_retry_4xx(monkeypatch, provider):
    session = FakeSession([FakeResponse(400)])
    monkeypatch.setattr(provider, "_http_client", session)
    monkeypatch.setattr("app.services.llm.openai_compatible._retry_delay", lambda attempt: 0)
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 2)

    result = provider.generate(LLMRequest(prompt="hi", max_tokens=16))

    assert session.calls == 1
    assert result.warning_code == "LLM_PROVIDER_NON_SUCCESS"


def test_generate_stream_retries_on_5xx(monkeypatch, provider):
    session = FakeSession([FakeResponse(502), FakeResponse(200)])
    monkeypatch.setattr(provider, "_http_client", session)
    monkeypatch.setattr("app.services.llm.openai_compatible._retry_delay", lambda attempt: 0)
    monkeypatch.setattr("app.services.llm.openai_compatible._max_retries", lambda: 2)

    # 第二次响应无 iter_lines，走到 LLM_OUTPUT_INVALID，但说明已重试
    chunks = list(provider.generate_stream(LLMRequest(prompt="hi", max_tokens=16)))

    assert session.calls == 2
    assert chunks[-1].finished
