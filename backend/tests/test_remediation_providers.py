from __future__ import annotations

import importlib
import importlib.util
from types import SimpleNamespace

import pytest

from app.services.remediation.provider import configured_provider


def _providers_module():
    spec = importlib.util.find_spec("app.services.remediation.providers")
    assert spec is not None, "统一 Provider 模块尚未实现"
    return importlib.import_module("app.services.remediation.providers")


class _MiniMaxClient:
    def __init__(self, *, api_key: str, model: str | None = None) -> None:
        self.api_key = api_key
        self.model = model or "minimax-test"
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "max_tokens": max_tokens,
            }
        )
        return "{\"rationale\":\"safe\"}"


class _DashScopeResponse:
    status_code = 200
    output = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="{\"rationale\":\"safe\"}"))]
    )


def test_minimax_adapter_preserves_the_unified_generate_contract():
    providers = _providers_module()
    client = _MiniMaxClient(api_key="test-key", model="MiniMax-test")
    provider = providers.MiniMaxProvider(client)

    output = provider.generate("prompt", system_prompt="system", max_tokens=321)

    assert output == "{\"rationale\":\"safe\"}"
    assert provider.provider_name == "minimax"
    assert provider.model == "MiniMax-test"
    assert client.calls == [
        {"prompt": "prompt", "system_prompt": "system", "max_tokens": 321}
    ]


def test_dashscope_adapter_normalizes_successful_message_content():
    providers = _providers_module()
    captured_request: dict[str, object] = {}

    def generation_call(**kwargs):
        captured_request.update(kwargs)
        return _DashScopeResponse()

    provider = providers.DashScopeProvider(
        api_key="test-key",
        model="qwen-test",
        generation_call=generation_call,
    )

    output = provider.generate("prompt", system_prompt="system", max_tokens=456)

    assert output == "{\"rationale\":\"safe\"}"
    assert provider.provider_name == "dashscope"
    assert provider.model == "qwen-test"
    assert captured_request == {
        "model": "qwen-test",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "prompt"},
        ],
        "result_format": "message",
        "api_key": "test-key",
        "max_tokens": 456,
    }


def test_configured_provider_selects_requested_dashscope_adapter(app, monkeypatch):
    providers = _providers_module()
    app.config.update(
        REMEDIATION_LLM_ENABLED=True,
        REMEDIATION_LLM_PROVIDER="dashscope",
        DASHSCOPE_API_KEY="test-key",
        DASHSCOPE_MODEL="qwen-test",
        MINIMAX_API_KEY="",
    )
    monkeypatch.setattr(providers, "_load_dashscope_generation_call", lambda: lambda **_kwargs: _DashScopeResponse())

    with app.app_context():
        provider = configured_provider(None)

    assert isinstance(provider, providers.DashScopeProvider)
    assert provider.provider_name == "dashscope"
    assert provider.model == "qwen-test"


@pytest.mark.parametrize("configured_name", ["unsupported", ""])
def test_unavailable_or_invalid_remote_provider_leaves_rule_based_fallback_available(app, configured_name):
    _providers_module()
    app.config.update(
        REMEDIATION_LLM_ENABLED=True,
        REMEDIATION_LLM_PROVIDER=configured_name,
        MINIMAX_API_KEY="",
        DASHSCOPE_API_KEY="",
    )

    with app.app_context():
        provider = configured_provider(None)

    assert provider is None

class _MiniMaxChatClient:
    model = "MiniMax-chat-test"

    def __init__(self):
        self.messages = None
        self.temperature = None
        self.max_tokens = None

    def chat(self, messages, *, temperature, max_tokens):
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        return {
            "status_code": 200,
            "output": {
                "choices": [{"message": {"content": "unified-answer"}}]
            },
            "usage": {"total_tokens": 9},
        }


def test_minimax_adapter_returns_standard_response_for_llm_request():
    providers = _providers_module()
    client = _MiniMaxChatClient()
    provider = providers.MiniMaxProvider(client)

    from app.services.llm import LLMRequest, LLMResponse

    response = provider.generate(
        LLMRequest(
            prompt="prompt",
            system_prompt="system",
            temperature=0.2,
            max_tokens=321,
        )
    )

    assert isinstance(response, LLMResponse)
    assert response.is_success is True
    assert response.text == "unified-answer"
    assert response.provider_name == "minimax"
    assert response.model == "MiniMax-chat-test"
    assert response.usage == {"total_tokens": 9}
    assert client.messages == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "prompt"},
    ]
    assert client.temperature == 0.2
    assert client.max_tokens == 321


def test_dashscope_adapter_returns_safe_warning_for_invalid_response():
    providers = _providers_module()

    class InvalidResponse:
        status_code = 200
        output = SimpleNamespace(choices=[])

    provider = providers.DashScopeProvider(
        api_key="test-key",
        model="qwen-test",
        generation_call=lambda **_kwargs: InvalidResponse(),
    )

    from app.services.llm import LLMRequest, LLMResponse

    response = provider.generate(LLMRequest(prompt="prompt"))

    assert isinstance(response, LLMResponse)
    assert response.is_success is False
    assert response.text is None
    assert response.warning_code == "LLM_OUTPUT_INVALID"


class _FailingMiniMaxClient:
    model = "MiniMax-failure-test"

    def chat(self, _messages, *, temperature, max_tokens):
        raise RuntimeError("secret prompt and api key must not escape")


def test_minimax_adapter_converts_request_exception_to_safe_warning():
    providers = _providers_module()
    provider = providers.MiniMaxProvider(_FailingMiniMaxClient())

    from app.services.llm import LLMRequest

    response = provider.generate(LLMRequest(prompt="sensitive prompt"))

    assert response.text is None
    assert response.warning_code == "LLM_PROVIDER_REQUEST_FAILED"
    assert "secret" not in repr(response).lower()


def test_dashscope_adapter_converts_non_success_status_to_safe_warning():
    providers = _providers_module()

    class ErrorResponse:
        status_code = 429
        message = "provider internal details"

    provider = providers.DashScopeProvider(
        api_key="test-key",
        model="qwen-test",
        generation_call=lambda **_kwargs: ErrorResponse(),
    )

    from app.services.llm import LLMRequest

    response = provider.generate(LLMRequest(prompt="prompt"))

    assert response.text is None
    assert response.status_code == 429
    assert response.warning_code == "LLM_PROVIDER_NON_SUCCESS"
    assert "internal details" not in repr(response)


def test_provider_selection_degrades_when_dashscope_sdk_is_missing(app, monkeypatch):
    providers = _providers_module()
    app.config.update(
        REMEDIATION_LLM_PROVIDER="dashscope",
        DASHSCOPE_API_KEY="test-key",
        DASHSCOPE_MODEL="qwen-test",
    )
    monkeypatch.setattr(
        providers,
        "_load_dashscope_generation_call",
        lambda: (_ for _ in ()).throw(ImportError("sdk missing")),
    )

    with app.app_context():
        assert providers.select_configured_provider() is None
