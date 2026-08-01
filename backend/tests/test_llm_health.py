from __future__ import annotations

from datetime import datetime, timezone
import time

from app.services.llm import LLMResponse
from app.services.llm.health import LLMProviderHealthChecker


class _Provider:
    provider_name = "minimax"
    model = "MiniMax-test"
    model_version = "test-version"
    accepts_llm_request = True

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def _checker(*, config=None, provider=None, sdk_available=True, **kwargs):
    current_config = {
        "MINIMAX_API_KEY": "",
        "MINIMAX_MODEL": "MiniMax-test",
        "DASHSCOPE_API_KEY": "",
        "DASHSCOPE_MODEL": "qwen-test",
    }
    current_config.update(config or {})
    return LLMProviderHealthChecker(
        config=current_config,
        provider_factories={"minimax": lambda: provider},
        sdk_checkers={"minimax": lambda: sdk_available},
        now=lambda: datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
        **kwargs,
    )


def test_missing_api_key_is_not_configured_and_passive_inspection_does_not_probe():
    checker = _checker()

    status = next(item for item in checker.inspect_configuration() if item.provider_name == "minimax")

    assert status.configured is False
    assert status.reachable is None
    assert status.status == "not_configured"
    assert status.warning_code == "LLM_PROVIDER_NOT_CONFIGURED"


def test_configured_provider_with_missing_sdk_is_reported_without_live_call():
    checker = _checker(
        config={"MINIMAX_API_KEY": "secret-key"},
        sdk_available=False,
    )

    status = next(item for item in checker.inspect_configuration() if item.provider_name == "minimax")

    assert status.configured is True
    assert status.sdk_available is False
    assert status.reachable is None
    assert status.status == "sdk_unavailable"
    assert status.warning_code == "LLM_PROVIDER_SDK_UNAVAILABLE"


def test_passive_inspection_never_constructs_provider():
    calls = []
    checker = LLMProviderHealthChecker(
        config={"MINIMAX_API_KEY": "secret-key", "MINIMAX_MODEL": "MiniMax-test"},
        provider_factories={"minimax": lambda: calls.append(True)},
        sdk_checkers={"minimax": lambda: True},
    )

    checker.inspect_configuration()

    assert calls == []


def test_configured_provider_is_not_verified_until_explicit_live_check():
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"})

    status = next(item for item in checker.inspect_configuration() if item.provider_name == "minimax")

    assert status.status == "configured_not_verified"
    assert status.warning_code == "LIVE_CHECK_NOT_RUN"
    assert status.reachable is None


def test_live_check_returns_safe_metadata_for_successful_provider():
    provider = _Provider(
        response=LLMResponse(
            text="OK",
            provider_name="minimax",
            model="MiniMax-test",
            model_version="test-version",
            status_code=200,
            latency_ms=12,
        )
    )
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"}, provider=provider, cooldown_seconds=0)

    status = checker.check_provider("minimax")
    payload = status.to_dict()

    assert status.status == "healthy"
    assert status.reachable is True
    assert status.warning_code is None
    assert payload["provider"] == "minimax"
    assert payload["model"] == "MiniMax-test"
    assert payload["latency_ms"] == 12
    assert "secret-key" not in repr(payload)
    assert len(provider.requests) == 1
    assert "secret-key" not in repr(provider.requests[0])
    assert "Return exactly" in provider.requests[0].prompt


def test_live_check_maps_timeout_to_safe_warning():
    provider = _Provider(error=TimeoutError("secret timeout details"))
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"}, provider=provider, cooldown_seconds=0)

    status = checker.check_provider("minimax")

    assert status.status == "timeout"
    assert status.reachable is False
    assert status.warning_code == "LLM_PROVIDER_TIMEOUT"
    assert "secret timeout details" not in repr(status.to_dict())


def test_live_check_maps_non_success_and_invalid_output():
    non_success = _Provider(
        response=LLMResponse(
            text=None,
            provider_name="minimax",
            model="MiniMax-test",
            status_code=503,
        )
    )
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"}, provider=non_success, cooldown_seconds=0)
    status = checker.check_provider("minimax")
    assert status.status == "provider_error"
    assert status.warning_code == "LLM_PROVIDER_NON_SUCCESS"

    invalid = _Provider(
        response=LLMResponse(
            text="not the probe response",
            provider_name="minimax",
            model="MiniMax-test",
            status_code=200,
        )
    )
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"}, provider=invalid, cooldown_seconds=0)
    status = checker.check_provider("minimax")
    assert status.status == "invalid_response"
    assert status.warning_code == "LLM_OUTPUT_INVALID"


def test_live_check_does_not_expose_unexpected_exception_body():
    provider = _Provider(error=RuntimeError("api-key secret and raw provider body"))
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"}, provider=provider, cooldown_seconds=0)

    status = checker.check_provider("minimax")
    payload = status.to_dict()

    assert status.warning_code == "LLM_PROVIDER_REQUEST_FAILED"
    assert "api-key secret" not in repr(payload)
    assert "raw provider body" not in repr(payload)


def test_explicit_live_check_is_rate_limited_per_provider():
    provider = _Provider(
        response=LLMResponse(
            text="OK",
            provider_name="minimax",
            model="MiniMax-test",
            status_code=200,
        )
    )
    checker = _checker(config={"MINIMAX_API_KEY": "secret-key"}, provider=provider, cooldown_seconds=30)

    first = checker.check_provider("minimax")
    second = checker.check_provider("minimax")

    assert first.status == "healthy"
    assert second.status == "rate_limited"
    assert second.warning_code == "LLM_HEALTH_RATE_LIMITED"
    assert len(provider.requests) == 1


def test_live_check_enforces_checker_timeout():
    class SlowProvider(_Provider):
        def generate(self, request):
            self.requests.append(request)
            time.sleep(0.1)
            return LLMResponse(
                text="OK",
                provider_name="minimax",
                model="MiniMax-test",
                status_code=200,
            )

    provider = SlowProvider()
    checker = _checker(
        config={"MINIMAX_API_KEY": "secret-key"},
        provider=provider,
        cooldown_seconds=0,
        live_check_timeout_seconds=0.01,
    )

    status = checker.check_provider("minimax")

    assert status.status == "timeout"
    assert status.warning_code == "LLM_PROVIDER_TIMEOUT"
    assert status.reachable is False
