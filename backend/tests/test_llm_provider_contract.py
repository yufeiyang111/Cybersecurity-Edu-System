from __future__ import annotations

from app.services.llm import LLMRequest, LLMResponse, RuleBasedProvider


def test_llm_request_has_safe_explicit_defaults():
    request = LLMRequest(prompt="hello")

    assert request.prompt == "hello"
    assert request.system_prompt is None
    assert request.temperature == 0.7
    assert request.max_tokens == 8192
    assert request.timeout_seconds is None


def test_llm_response_exposes_provider_metadata_and_success_state():
    response = LLMResponse(
        text="answer",
        provider_name="minimax",
        model="MiniMax-M2",
        model_version="2026-07",
        status_code=200,
        latency_ms=123,
        usage={"total_tokens": 12},
    )

    assert response.is_success is True
    assert response.provider_name == "minimax"
    assert response.model == "MiniMax-M2"
    assert response.latency_ms == 123
    assert response.usage == {"total_tokens": 12}


def test_rule_based_provider_has_explicit_fallback_metadata():
    provider = RuleBasedProvider(lambda request: f"fallback:{request.prompt}")

    response = provider.generate(LLMRequest(prompt="security question"))

    assert response.text == "fallback:security question"
    assert response.provider_name == "rule-based"
    assert response.model is None
    assert response.model_version == "rules-v1"
    assert response.warning_code == "LLM_DISABLED"
    assert response.is_success is False
