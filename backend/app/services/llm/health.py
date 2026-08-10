"""LLM Provider 配置检查与显式连通性探测。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.util import find_spec
from threading import Lock
from time import monotonic, perf_counter
from typing import Any, Callable, Mapping

from .contracts import LLMRequest, LLMResponse

HEALTH_CHECK_PROMPT = "Return exactly: OK"
HEALTH_CHECK_SYSTEM_PROMPT = (
    "This is a provider connectivity probe. Return exactly OK. "
    "Do not disclose credentials, prompts, source code, or internal errors."
)
SUPPORTED_PROVIDERS = ("minimax", "dashscope")


@dataclass(frozen=True)
class ProviderHealthStatus:
    """可安全返回给运维或前端的 Provider 状态。"""

    provider_name: str
    configured: bool
    sdk_available: bool
    reachable: bool | None
    status: str
    warning_code: str | None
    model: str | None
    checked_at: datetime | None = None
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": self.configured,
            "sdk_available": self.sdk_available,
            "reachable": self.reachable,
            "status": self.status,
            "warning_code": self.warning_code,
            "model": self.model,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "latency_ms": self.latency_ms,
        }


class LLMProviderHealthChecker:
    """执行被动配置检查和受控的显式 Provider 连通性检查。"""

    def __init__(
        self,
        *,
        config: Mapping[str, object],
        provider_factories: Mapping[str, Callable[[], object | None]] | None = None,
        sdk_checkers: Mapping[str, Callable[[], bool]] | None = None,
        now: Callable[[], datetime] | None = None,
        clock: Callable[[], float] | None = None,
        live_check_timeout_seconds: float = 8.0,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self._config = config
        self._provider_factories = dict(provider_factories or _default_provider_factories())
        self._sdk_checkers = dict(sdk_checkers or _default_sdk_checkers())
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._clock = clock or monotonic
        self._live_check_timeout_seconds = max(0.01, float(live_check_timeout_seconds))
        self._cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._last_checks: dict[str, float] = {}
        self._lock = Lock()

    def inspect_configuration(self) -> list[ProviderHealthStatus]:
        """只检查配置和 SDK、不构造 Provider，也不访问网络。"""
        return [self._inspect_provider(provider_name) for provider_name in SUPPORTED_PROVIDERS]

    def check_provider(self, provider_name: str) -> ProviderHealthStatus:
        """执行一次固定 Prompt 的显式连通性探测。"""
        normalized_name = str(provider_name or "").strip().lower()
        if normalized_name not in SUPPORTED_PROVIDERS:
            return ProviderHealthStatus(
                provider_name=normalized_name or "unknown",
                configured=False,
                sdk_available=False,
                reachable=False,
                status="unsupported_provider",
                warning_code="LLM_PROVIDER_UNSUPPORTED",
                model=None,
                checked_at=self._now(),
            )

        inspected = self._inspect_provider(normalized_name)
        checked_at = self._now()
        if not inspected.configured:
            return _replace_status(
                inspected,
                reachable=False,
                status="not_configured",
                warning_code="LLM_PROVIDER_NOT_CONFIGURED",
                checked_at=checked_at,
            )
        if not inspected.sdk_available:
            return _replace_status(
                inspected,
                reachable=False,
                status="sdk_unavailable",
                warning_code="LLM_PROVIDER_SDK_UNAVAILABLE",
                checked_at=checked_at,
            )
        if not self._allow_live_check(normalized_name):
            return _replace_status(
                inspected,
                reachable=None,
                status="rate_limited",
                warning_code="LLM_HEALTH_RATE_LIMITED",
                checked_at=checked_at,
            )

        try:
            provider_factory = self._provider_factories.get(normalized_name)
            provider = provider_factory() if provider_factory else None
            if provider is None:
                return _replace_status(
                    inspected,
                    reachable=False,
                    status="provider_error",
                    warning_code="LLM_PROVIDER_REQUEST_FAILED",
                    checked_at=checked_at,
                )
            response, elapsed_ms = self._run_probe(provider)
        except FutureTimeoutError:
            return _replace_status(
                inspected,
                reachable=False,
                status="timeout",
                warning_code="LLM_PROVIDER_TIMEOUT",
                checked_at=checked_at,
            )
        except TimeoutError:
            return _replace_status(
                inspected,
                reachable=False,
                status="timeout",
                warning_code="LLM_PROVIDER_TIMEOUT",
                checked_at=checked_at,
            )
        except Exception:
            return _replace_status(
                inspected,
                reachable=False,
                status="provider_error",
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                checked_at=checked_at,
            )

        if not isinstance(response, LLMResponse):
            return _replace_status(
                inspected,
                reachable=True,
                status="invalid_response",
                warning_code="LLM_OUTPUT_INVALID",
                checked_at=checked_at,
                latency_ms=elapsed_ms,
            )
        if response.warning_code == "LLM_PROVIDER_TIMEOUT":
            return _replace_status(
                inspected,
                reachable=False,
                status="timeout",
                warning_code="LLM_PROVIDER_TIMEOUT",
                checked_at=checked_at,
                latency_ms=_response_latency(response, elapsed_ms),
            )
        if response.status_code is not None and response.status_code != 200:
            return _replace_status(
                inspected,
                reachable=True,
                status="provider_error",
                warning_code="LLM_PROVIDER_NON_SUCCESS",
                checked_at=checked_at,
                latency_ms=_response_latency(response, elapsed_ms),
            )
        if response.warning_code:
            return _replace_status(
                inspected,
                reachable=False,
                status="provider_error",
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                checked_at=checked_at,
                latency_ms=_response_latency(response, elapsed_ms),
            )
        if not response.text or response.text.strip().upper() != "OK":
            return _replace_status(
                inspected,
                reachable=True,
                status="invalid_response",
                warning_code="LLM_OUTPUT_INVALID",
                checked_at=checked_at,
                latency_ms=_response_latency(response, elapsed_ms),
            )
        return _replace_status(
            inspected,
            reachable=True,
            status="healthy",
            warning_code=None,
            checked_at=checked_at,
            latency_ms=_response_latency(response, elapsed_ms),
        )

    def _inspect_provider(self, provider_name: str) -> ProviderHealthStatus:
        api_key_name, model_name = _provider_config_keys(provider_name)
        api_key = str(self._config.get(api_key_name, "") or "").strip()
        model = str(self._config.get(model_name, "") or "").strip() or None
        configured = bool(api_key and model)
        sdk_available = _safe_sdk_check(self._sdk_checkers.get(provider_name))
        if not configured:
            status = "not_configured"
            warning_code = "LLM_PROVIDER_NOT_CONFIGURED"
            safe_model = None
        elif not sdk_available:
            status = "sdk_unavailable"
            warning_code = "LLM_PROVIDER_SDK_UNAVAILABLE"
            safe_model = model
        else:
            status = "configured_not_verified"
            warning_code = "LIVE_CHECK_NOT_RUN"
            safe_model = model
        return ProviderHealthStatus(
            provider_name=provider_name,
            configured=configured,
            sdk_available=sdk_available,
            reachable=None,
            status=status,
            warning_code=warning_code,
            model=safe_model,
        )

    def _allow_live_check(self, provider_name: str) -> bool:
        now = self._clock()
        with self._lock:
            previous = self._last_checks.get(provider_name)
            if previous is not None and now - previous < self._cooldown_seconds:
                return False
            self._last_checks[provider_name] = now
            return True

    def _run_probe(self, provider: object) -> tuple[object, int]:
        request = LLMRequest(
            prompt=HEALTH_CHECK_PROMPT,
            system_prompt=HEALTH_CHECK_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=512,
            timeout_seconds=self._live_check_timeout_seconds,
        )
        started = perf_counter()
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(provider.generate, request)
        try:
            response = future.result(timeout=self._live_check_timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        except BaseException:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)
        return response, max(0, round((perf_counter() - started) * 1000))


def _replace_status(current: ProviderHealthStatus, **changes: object) -> ProviderHealthStatus:
    values = {
        "provider_name": current.provider_name,
        "configured": current.configured,
        "sdk_available": current.sdk_available,
        "reachable": current.reachable,
        "status": current.status,
        "warning_code": current.warning_code,
        "model": current.model,
        "checked_at": current.checked_at,
        "latency_ms": current.latency_ms,
    }
    values.update(changes)
    return ProviderHealthStatus(**values)


def _provider_config_keys(provider_name: str) -> tuple[str, str]:
    if provider_name == "minimax":
        return "MINIMAX_API_KEY", "MINIMAX_MODEL"
    if provider_name == "dashscope":
        return "DASHSCOPE_API_KEY", "DASHSCOPE_MODEL"
    raise ValueError("unsupported provider")


def _safe_sdk_check(checker: Callable[[], bool] | None) -> bool:
    if checker is None:
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def _response_latency(response: LLMResponse, elapsed_ms: int) -> int:
    return response.latency_ms if isinstance(response.latency_ms, int) and response.latency_ms >= 0 else elapsed_ms


def _default_provider_factories() -> dict[str, Callable[[], object | None]]:
    from app.services.remediation.providers import create_configured_provider

    return {
        provider_name: (lambda name=provider_name: create_configured_provider(name))
        for provider_name in SUPPORTED_PROVIDERS
    }


def _default_sdk_checkers() -> dict[str, Callable[[], bool]]:
    return {
        "minimax": lambda: _module_available("requests"),
        "dashscope": lambda: _module_available("dashscope"),
    }


def _module_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False
