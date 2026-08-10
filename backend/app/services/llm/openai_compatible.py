"""OpenAI-compatible chat completion adapter with safe response handling."""
from __future__ import annotations

import dataclasses
import json
import re
import time
from time import perf_counter
from typing import Any, Iterator

import requests
from flask import current_app, has_app_context

from .contracts import LLMRequest, LLMResponse, LLMStreamChunk
from .encoding_guard import safe_decode
from .internal_reasoning_boundary import project
from .usage_normalizer import normalize_usage

_DEFAULT_MAX_TOKENS = 8192


def _should_retry_status(status_code: int) -> bool:
    """可重试状态码：429 限流、5xx 服务端错误。"""
    return status_code in (429,) or status_code >= 500


def _max_retries() -> int:
    if has_app_context():
        return max(0, int(current_app.config.get("LLM_MAX_RETRIES", 2)))
    return 2


def _retry_delay(attempt: int) -> float:
    """指数退避延迟（秒）：0.8, 1.6, 3.2 ..."""
    if has_app_context():
        base = float(current_app.config.get("LLM_RETRY_BASE_DELAY", 0.8))
    else:
        base = 0.8
    return base * (2 ** attempt)


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


class _ThinkStreamFilter:
    """Stream-safe stripper for <think>...</think> blocks split across chunks.

    MiniMax emits reasoning inline inside content with <think> tags that can
    span multiple SSE chunks; buffering until the closing tag keeps reasoning
    out of the visible stream (mirrors LabexAgent's thinkParser).
    """

    _OPEN_RE = re.compile(r"(?is)<\s*think(?:ing)?(?:\s[^>]*)?>")
    _CLOSE_RE = re.compile(r"(?is)</\s*think(?:ing)?(?:\s[^>]*)?\s*>")

    def __init__(self) -> None:
        self._buffer = ""
        self._in_think = False

    def push(self, delta: str) -> str:
        """Return visible text; reasoning content is buffered and dropped."""
        self._buffer += delta or ""
        visible = ""
        while True:
            if self._in_think:
                match = self._CLOSE_RE.search(self._buffer)
                if match is None:
                    break
                self._buffer = self._buffer[match.end():]
                self._in_think = False
                continue
            match = self._OPEN_RE.search(self._buffer)
            if match is None:
                visible += self._buffer
                self._buffer = ""
                break
            visible += self._buffer[:match.start()]
            self._buffer = self._buffer[match.end():]
            self._in_think = True
        return visible

    def flush(self) -> str:
        """Visible remainder when the stream ends (unclosed thinking dropped)."""
        visible = "" if self._in_think else self._buffer
        self._buffer = ""
        self._in_think = False
        return visible


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
        max_tokens: int | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.base_url = _completion_url(base_url)
        self._api_key = api_key
        self._http_client = http_client or requests.Session()
        self.provider_config_id = provider_config_id
        self.user_id = user_id
        self.operation = operation
        self.max_tokens = max_tokens

    def _apply_provider_max_tokens(self, request: LLMRequest) -> LLMRequest:
        """Provider 级 max_tokens 作为该 Provider 的输出上限（封顶）。

        用户配置了 max_tokens 时，任何请求都被限制在其内（取较小值）；
        未配置时维持请求自身值。探测类小请求（如 512）不受大值影响。
        """
        if self.max_tokens is None:
            return request
        capped = min(request.max_tokens, self.max_tokens)
        if capped == request.max_tokens:
            return request
        return dataclasses.replace(request, max_tokens=capped)

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = perf_counter()
        request = self._apply_provider_max_tokens(request)
        payload = _payload(request, self.model, stream=False)
        _log(current_app.logger.warning if has_app_context() else None,
             "OpenAICompatibleProvider.generate called (provider=%s, base_url=%s, model=%s)",
             self.provider_name, self.base_url, self.model)
        max_retries = _max_retries()
        for attempt in range(max_retries + 1):
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
                    raw_text = safe_decode(getattr(response, "content", b""))
                _log(current_app.logger.warning if has_app_context() else None,
                     "OpenAICompatibleProvider HTTP raw response (provider=%s, status=%s, raw=%r)",
                     self.provider_name, getattr(response, "status_code", None), raw_text[:1500])
                if _response_too_large(response):
                    return _failure(self, "LLM_PROVIDER_RESPONSE_TOO_LARGE", started, status_code=413)
                status_code = _status_code(response)
                if status_code != 200:
                    if _should_retry_status(status_code) and attempt < max_retries:
                        _log(
                            current_app.logger.warning if has_app_context() else None,
                            "LLM retry (provider=%s, attempt=%s/%s, status=%s)",
                            self.provider_name, attempt + 1, max_retries, status_code,
                        )
                        time.sleep(_retry_delay(attempt))
                        continue
                    return _failure(
                        self,
                        "LLM_PROVIDER_NON_SUCCESS",
                        started,
                        status_code=status_code,
                    )
                try:
                    body = response.json()
                except (TypeError, ValueError):
                    return _failure(self, "LLM_OUTPUT_INVALID", started, status_code=200)
                return _success_response(self, body, started)
            except requests.Timeout:
                if attempt < max_retries:
                    _log(
                        current_app.logger.warning if has_app_context() else None,
                        "LLM retry on timeout (provider=%s, attempt=%s/%s)",
                        self.provider_name, attempt + 1, max_retries,
                    )
                    time.sleep(_retry_delay(attempt))
                    continue
                return _failure(self, "LLM_PROVIDER_TIMEOUT", started)
            except requests.RequestException:
                if attempt < max_retries:
                    _log(
                        current_app.logger.warning if has_app_context() else None,
                        "LLM retry on request failure (provider=%s, attempt=%s/%s)",
                        self.provider_name, attempt + 1, max_retries,
                    )
                    time.sleep(_retry_delay(attempt))
                    continue
                return _failure(self, "LLM_PROVIDER_REQUEST_FAILED", started)
        return _failure(self, "LLM_PROVIDER_REQUEST_FAILED", started)

    def generate_stream(self, request: LLMRequest) -> Iterator[LLMStreamChunk]:
        started = perf_counter()
        payload = _payload(request, self.model, stream=True)
        max_retries = _max_retries()

        # 连接阶段：429/5xx/超时 指数退避重试
        response = None
        for attempt in range(max_retries + 1):
            try:
                response = self._http_client.post(
                    self.base_url,
                    headers=self._headers(stream=True),
                    json=payload,
                    timeout=_timeout(),
                    allow_redirects=False,
                    stream=True,
                )
                if (
                    getattr(response, "status_code", None) is not None
                    and 400 <= getattr(response, "status_code") < 500
                    and _body_mentions_stream_options(response)
                ):
                    degraded = dict(payload)
                    degraded.pop("stream_options", None)
                    response = self._http_client.post(
                        self.base_url,
                        headers=self._headers(stream=True),
                        json=degraded,
                        timeout=_timeout(),
                        allow_redirects=False,
                        stream=True,
                    )
                status_code = getattr(response, "status_code", None)
                if status_code is not None and status_code != 200:
                    if _should_retry_status(status_code) and attempt < max_retries:
                        _log(
                            current_app.logger.warning if has_app_context() else None,
                            "LLM stream retry (provider=%s, attempt=%s/%s, status=%s)",
                            self.provider_name, attempt + 1, max_retries, status_code,
                        )
                        time.sleep(_retry_delay(attempt))
                        continue
                    yield LLMStreamChunk(
                        finished=True,
                        warning_code="LLM_PROVIDER_NON_SUCCESS",
                    )
                    return
                break
            except requests.Timeout:
                if attempt < max_retries:
                    _log(
                        current_app.logger.warning if has_app_context() else None,
                        "LLM stream retry on timeout (provider=%s, attempt=%s/%s)",
                        self.provider_name, attempt + 1, max_retries,
                    )
                    time.sleep(_retry_delay(attempt))
                    continue
                yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_TIMEOUT")
                return
            except requests.RequestException:
                if attempt < max_retries:
                    _log(
                        current_app.logger.warning if has_app_context() else None,
                        "LLM stream retry on request failure (provider=%s, attempt=%s/%s)",
                        self.provider_name, attempt + 1, max_retries,
                    )
                    time.sleep(_retry_delay(attempt))
                    continue
                yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_REQUEST_FAILED")
                return

        # 流解析阶段：已开始产出内容后失败不再重试（避免重复内容）
        try:
            iterator = getattr(response, "iter_lines", None)
            if not callable(iterator):
                yield LLMStreamChunk(finished=True, warning_code="LLM_OUTPUT_INVALID")
                return

            seen_bytes = 0
            usage = {}
            think_filter = _ThinkStreamFilter()
            # 注意：不使用 iter_lines(decode_unicode=True) —— 它会按响应头推断编码，
            # 响应头缺少 charset 时回退 ISO-8859-1，中文会被解成乱码。
            # 这里按字节流读取，统一用 UTF-8 解码。
            for raw_line in iterator(decode_unicode=False):
                if not raw_line:
                    continue
                line = safe_decode(raw_line)
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
                    normalized_usage = normalize_usage(body["usage"])
                    if normalized_usage:
                        usage = normalized_usage
                choice = _first_choice(body)
                delta = choice.get("delta") if isinstance(choice, dict) else {}
                delta = delta if isinstance(delta, dict) else {}
                raw_content = str(delta.get("content") or "")
                visible_content = think_filter.push(raw_content)
                if visible_content or delta.get("reasoning_content"):
                    yield LLMStreamChunk(
                        delta=visible_content,
                        reasoning_delta=str(delta.get("reasoning_content") or ""),
                        usage=usage,
                    )
            finished_visible = think_filter.flush()
            if finished_visible:
                yield LLMStreamChunk(delta=finished_visible, usage=usage)
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
    if stream:
        body["stream_options"] = {"include_usage": True}
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
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        if finish_reason == "length":
            warning_code = "LLM_OUTPUT_TRUNCATED"
        else:
            warning_code = "LLM_OUTPUT_INVALID"
        _log(
            current_app.logger.warning if has_app_context() else None,
            "OpenAICompatible: empty content from %s (base_url=%s, model=%s, warning_code=%s). "
            "choices=%r, body_keys=%r, choice=%r, message=%r, content=%r, reasoning=%r",
            provider.provider_name, provider.base_url, provider.model, warning_code,
            body.get("choices"), list(body.keys()),
            choice, message, repr(raw_content), repr(reasoning),
        )
        return _failure(provider, warning_code, started, status_code=200)
    raw_usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    usage = normalize_usage(raw_usage) or {}
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


def _body_mentions_stream_options(response: object) -> bool:
    """True when a 4xx body complains about stream_options / include_usage."""
    raw = getattr(response, "text", None)
    if raw is None:
        raw = getattr(response, "content", b"")
        raw = safe_decode(raw) if isinstance(raw, (bytes, bytearray)) else ""
    lower = str(raw or "").lower()
    return (
        "stream_options" in lower
        or "include_usage" in lower
        or "unknown field" in lower
        or "unrecognized" in lower
        or "unsupported parameter" in lower
        or "extra inputs are not permitted" in lower
    )


def _status_code(response: object) -> int | None:
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _latency_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
