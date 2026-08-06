"""OpenAI-compatible chat completion adapter with safe response handling."""
from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Iterator

import requests
from flask import current_app, has_app_context

from .contracts import LLMRequest, LLMResponse, LLMStreamChunk
from .internal_reasoning_boundary import project


def _log(method, msg, *args, **kwargs) -> None:
    if method is not None:
        method(msg, *args, **kwargs)


def _raw_log(provider: OpenAICompatibleProvider, response_text: str) -> None:
    """打印 provider 返回的原始文本，用于诊断格式差异。"""
    _log(
        current_app.logger.warning if has_app_context() else None,
        "[DIAG] MiniMax raw response from %s (base_url=%s, model=%s):\n%s",
        provider.provider_name,
        provider.base_url,
        provider.model,
        response_text[:2000],
    )


class OpenAICompatibleProvider:
    """Adapt /chat/completions compatible services to the shared LLM contract."""

    model_version = None
    accepts_llm_request = True

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
        model: str,
        http_client: object | None = None,
        provider_config_id: int | None = None,
        user_id: int | None = None,
        operation: str = "unknown",
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.base_url = _completion_url(base_url)
        self._api_key = api_key
        self._http_client = http_client or requests.Session()
        self.provider_config_id = provider_config_id
        self.user_id = user_id
        self.operation = operation

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = perf_counter()
        payload = _payload(request, self.model, stream=False)
        _log(current_app.logger.warning if has_app_context() else None,
             "OpenAICompatibleProvider.generate called (provider=%s, base_url=%s, model=%s)",
             self.provider_name, self.base_url, self.model)
        try:
            response = self._http_client.post(
                self.base_url,
                headers=self._headers(stream=False),
                json=payload,
                timeout=_timeout(),
                allow_redirects=False,
            )
            raw_text = getattr(response, "text", None)
            if raw_text is None:
                raw_text = getattr(response, "content", b"").decode("utf-8", errors="replace")
            _log(current_app.logger.warning if has_app_context() else None,
                 "OpenAICompatibleProvider HTTP raw response (provider=%s, status=%s, raw=%r)",
                 self.provider_name, getattr(response, "status_code", None), raw_text[:1500])
            if _response_too_large(response):
                return _failure(self, "LLM_PROVIDER_RESPONSE_TOO_LARGE", started, status_code=413)
            if getattr(response, "status_code", None) != 200:
                return _failure(
                    self,
                    "LLM_PROVIDER_NON_SUCCESS",
                    started,
                    status_code=_status_code(response),
                )
            try:
                body = response.json()
            except (TypeError, ValueError):
                return _failure(self, "LLM_OUTPUT_INVALID", started, status_code=200)
            return _success_response(self, body, started)
        except requests.Timeout:
            return _failure(self, "LLM_PROVIDER_TIMEOUT", started)
        except requests.RequestException:
            return _failure(self, "LLM_PROVIDER_REQUEST_FAILED", started)

    def generate_stream(self, request: LLMRequest) -> Iterator[LLMStreamChunk]:
        started = perf_counter()
        payload = _payload(request, self.model, stream=True)
        try:
            response = self._http_client.post(
                self.base_url,
                headers=self._headers(stream=True),
                json=payload,
                timeout=_timeout(),
                allow_redirects=False,
                stream=True,
            )
            if getattr(response, "status_code", None) != 200:
                yield LLMStreamChunk(
                    finished=True,
                    warning_code="LLM_PROVIDER_NON_SUCCESS",
                )
                return
            iterator = getattr(response, "iter_lines", None)
            if not callable(iterator):
                yield LLMStreamChunk(finished=True, warning_code="LLM_OUTPUT_INVALID")
                return

            seen_bytes = 0
            completed = False
            usage = {}
            for raw_line in iterator(decode_unicode=True):
                line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line)
                seen_bytes += len(line.encode("utf-8"))
                if seen_bytes > _max_response_bytes():
                    yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_RESPONSE_TOO_LARGE")
                    return
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                if data == "[DONE]":
                    completed = True
                    yield LLMStreamChunk(finished=True, usage=usage)
                    return
                try:
                    body = json.loads(data)
                except (TypeError, ValueError):
                    continue
                if body.get("error"):
                    yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_NON_SUCCESS")
                    return
                if isinstance(body.get("usage"), dict):
                    usage = body["usage"]
                choice = _first_choice(body)
                delta = choice.get("delta") if isinstance(choice, dict) else {}
                delta = delta if isinstance(delta, dict) else {}
                finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
                if delta.get("content") or delta.get("reasoning_content"):
                    yield LLMStreamChunk(
                        delta=str(delta.get("content") or ""),
                        reasoning_delta=str(delta.get("reasoning_content") or ""),
                        usage=usage,
                    )
                if finish_reason:
                    completed = True
            if not completed:
                yield LLMStreamChunk(finished=True, usage=usage)
        except requests.Timeout:
            yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_TIMEOUT")
        except requests.RequestException:
            yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_REQUEST_FAILED")

    def _headers(self, *, stream: bool) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }


def _completion_url(base_url: str) -> str:
    normalized = str(base_url or "").rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _payload(request: LLMRequest, model: str, *, stream: bool) -> dict[str, Any]:
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": stream,
    }
    if request.prompt_cache_key:
        body["prompt_cache_key"] = request.prompt_cache_key
    return body


def _success_response(provider: OpenAICompatibleProvider, body: object, started: float) -> LLMResponse:
    _log(
        current_app.logger.info if has_app_context() else None,
        "OpenAICompatible _success_response (provider=%s, body_type=%s, body_keys=%s, body=%r)",
        provider.provider_name,
        type(body).__name__,
        list(body.keys()) if isinstance(body, dict) else "N/A",
        body,
    )
    if not isinstance(body, dict):
        _log(
            current_app.logger.warning if has_app_context() else None,
            "OpenAICompatible: response body is not a dict (provider=%s, type=%s)",
            provider.provider_name, type(body).__name__,
        )
        return _failure(provider, "LLM_OUTPUT_INVALID", started, status_code=200)
    choice = _first_choice(body)
    message = choice.get("message") if isinstance(choice, dict) else {}
    message = message if isinstance(message, dict) else {}
    raw_content = message.get("content") or body.get("text") or ""
    reasoning_content = message.get("reasoning_content") if isinstance(message.get("reasoning_content"), str) else None
    _log(
        current_app.logger.warning if has_app_context() else None,
        "[DIAG] project input raw_content=%r, reasoning_content=%r",
        raw_content[:500], reasoning_content,
    )
    visible, reasoning = project(raw_content, reasoning_content)
    if not visible.strip():
        _log(
            current_app.logger.warning if has_app_context() else None,
            "OpenAICompatible: empty content from %s (base_url=%s, model=%s). "
            "choices=%r, body_keys=%r, choice=%r, message=%r, content=%r, reasoning=%r",
            provider.provider_name, provider.base_url, provider.model,
            body.get("choices"), list(body.keys()),
            choice, message, repr(raw_content), repr(reasoning),
        )
        return _failure(provider, "LLM_OUTPUT_INVALID", started, status_code=200)
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    return LLMResponse(
        text=visible,
        provider_name=provider.provider_name,
        model=str(body.get("model") or provider.model),
        status_code=200,
        latency_ms=_latency_ms(started),
        usage=usage,
        finish_reason=choice.get("finish_reason") if isinstance(choice, dict) else None,
        reasoning=reasoning or None,
    )


def _failure(
    provider: OpenAICompatibleProvider,
    warning_code: str,
    started: float,
    *,
    status_code: int | None = None,
) -> LLMResponse:
    _log(
        current_app.logger.warning if has_app_context() else None,
        "OpenAICompatible provider failure (provider=%s, base_url=%s, model=%s, "
        "warning_code=%r, status_code=%s, latency_ms=%s)",
        provider.provider_name, provider.base_url, provider.model,
        warning_code, status_code, _latency_ms(started),
    )
    return LLMResponse(
        text=None,
        provider_name=provider.provider_name,
        model=provider.model,
        status_code=status_code,
        warning_code=warning_code,
        latency_ms=_latency_ms(started),
    )


def _first_choice(body: dict[str, Any]) -> dict[str, Any]:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {}
    return choices[0]


def _timeout() -> tuple[float, float]:
    defaults = (5.0, 60.0)
    if not has_app_context():
        return defaults
    return (
        max(0.1, float(current_app.config.get("LLM_PROVIDER_CONNECT_TIMEOUT_SECONDS", defaults[0]))),
        max(0.1, float(current_app.config.get("LLM_PROVIDER_READ_TIMEOUT_SECONDS", defaults[1]))),
    )


def _max_response_bytes() -> int:
    if not has_app_context():
        return 2 * 1024 * 1024
    return max(1024, int(current_app.config.get("LLM_PROVIDER_MAX_RESPONSE_BYTES", 2 * 1024 * 1024)))


def _response_too_large(response: object) -> bool:
    content = getattr(response, "content", b"")
    return isinstance(content, (bytes, bytearray)) and len(content) > _max_response_bytes()


def _status_code(response: object) -> int | None:
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _latency_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
