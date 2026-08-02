"""统一远程 LLM Provider 的选择与文本生成适配。"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from time import perf_counter
from typing import Any

from flask import current_app

from app.services.llm import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    ProviderUnavailableError,
)

# 修复 Agent 仅依赖这个最小文本生成契约。
TextGenerationProvider = LLMProvider


class MiniMaxProvider:
    """将既有 MiniMax 客户端适配为统一 Provider 契约。"""

    provider_name = "minimax"
    model_version = None
    accepts_llm_request = True

    def __init__(self, client: object) -> None:
        self._client = client
        self.model = _metadata_value(client, "model")

    def generate(
        self,
        request_or_prompt: LLMRequest | str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse | str:
        legacy_call = isinstance(request_or_prompt, str)
        request = _coerce_request(request_or_prompt, system_prompt, max_tokens, temperature)
        started = perf_counter()
        try:
            if callable(getattr(self._client, "chat", None)):
                chat_kwargs = {
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                }
                if request.timeout_seconds is not None:
                    chat_kwargs["timeout_seconds"] = request.timeout_seconds
                raw_response = self._client.chat(_messages(request), **chat_kwargs)
                response = _minimax_response(raw_response, self.model, started)
            else:
                raw_text = self._client.generate(
                    request.prompt,
                    system_prompt=request.system_prompt,
                    max_tokens=request.max_tokens,
                )
                response = _text_response(
                    raw_text,
                    provider_name=self.provider_name,
                    model=self.model,
                    started=started,
                )
        except Exception:
            response = _failure_response(
                provider_name=self.provider_name,
                model=self.model,
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                started=started,
            )
        return _legacy_result(response) if legacy_call else response

    def generate_stream(
        self,
        request: LLMRequest,
    ) -> Iterator[LLMStreamChunk]:
        """流式生成，逐块产出增量；客户端不支持流式时降级为一次性输出。"""
        chat_stream = getattr(self._client, "chat_stream", None)
        if not callable(chat_stream):
            response = self.generate(request)
            if isinstance(response, LLMResponse) and response.is_success:
                yield LLMStreamChunk(delta=response.text or "", finished=True)
                return
            yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_REQUEST_FAILED")
            return

        chat_kwargs: dict[str, Any] = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.timeout_seconds is not None:
            chat_kwargs["timeout_seconds"] = request.timeout_seconds
        try:
            for event in chat_stream(_messages(request), **chat_kwargs):
                event_dict = event if isinstance(event, dict) else {}
                status_code = _as_int(event_dict.get("status_code"))
                yield LLMStreamChunk(
                    delta=str(event_dict.get("delta") or ""),
                    reasoning_delta=str(event_dict.get("reasoning_delta") or ""),
                    finished=bool(event_dict.get("finish")),
                    warning_code=None if status_code == 200 else "LLM_PROVIDER_NON_SUCCESS",
                )
                if event_dict.get("finish"):
                    return
        except Exception:
            yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_REQUEST_FAILED")


class DashScopeProvider:
    """将 DashScope Generation 响应归一化为统一文本输出。"""

    provider_name = "dashscope"
    model_version = None
    accepts_llm_request = True

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        generation_call: Callable[..., object],
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._generation_call = generation_call

    def generate(
        self,
        request_or_prompt: LLMRequest | str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse | str:
        legacy_call = isinstance(request_or_prompt, str)
        request = _coerce_request(request_or_prompt, system_prompt, max_tokens, temperature)
        started = perf_counter()
        messages = _messages(request)
        try:
            generation_kwargs = {
                "model": self.model,
                "messages": messages,
                "result_format": "message",
                "api_key": self._api_key,
                "max_tokens": request.max_tokens,
            }
            if not legacy_call:
                generation_kwargs["temperature"] = request.temperature
            raw_response = self._generation_call(**generation_kwargs)
            response = _dashscope_response(raw_response, self.model, started)
        except Exception:
            response = _failure_response(
                provider_name=self.provider_name,
                model=self.model,
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                started=started,
            )
        return _legacy_result(response) if legacy_call else response

    def generate_stream(
        self,
        request: LLMRequest,
    ) -> Iterator[LLMStreamChunk]:
        """流式生成（incremental_output），逐块产出增量。"""
        messages = _messages(request)
        try:
            stream = self._generation_call(
                model=self.model,
                messages=messages,
                result_format="message",
                api_key=self._api_key,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=True,
                incremental_output=True,
            )
        except Exception:
            yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_REQUEST_FAILED")
            return

        try:
            for item in stream:
                status_code = _as_int(_read_value(item, "status_code"))
                if status_code != 200:
                    yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_NON_SUCCESS")
                    return
                message = _stream_message(item)
                content = _read_value(message, "content")
                thinking = _read_value(message, "thinking")
                yield LLMStreamChunk(
                    delta=str(content) if isinstance(content, str) else "",
                    reasoning_delta=str(thinking) if isinstance(thinking, str) else "",
                )
            yield LLMStreamChunk(finished=True)
        except Exception:
            yield LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_REQUEST_FAILED")


def create_configured_provider(provider_name: str) -> LLMProvider | None:
    """??????????? Provider?????????"""
    normalized_name = str(provider_name or "").strip().lower()
    return _create_provider(normalized_name)


def select_configured_provider() -> LLMProvider | None:
    """根据当前应用配置创建一个可用的远程 Provider。"""
    configured_name = str(current_app.config.get("REMEDIATION_LLM_PROVIDER", "")).strip().lower()
    if configured_name and configured_name not in {"minimax", "dashscope"}:
        return None

    candidates = (configured_name,) if configured_name else ("minimax", "dashscope")
    for provider_name in candidates:
        provider = _create_provider(provider_name)
        if provider is not None:
            return provider
    return None


def _create_provider(provider_name: str) -> LLMProvider | None:
    if provider_name == "minimax":
        return _create_minimax_provider()
    if provider_name == "dashscope":
        return _create_dashscope_provider()
    return None


def _create_minimax_provider() -> MiniMaxProvider | None:
    api_key = str(current_app.config.get("MINIMAX_API_KEY", "")).strip()
    if not api_key:
        return None

    from app.services.minimax_llm import MiniMaxLLM

    model = str(current_app.config.get("MINIMAX_MODEL", "")).strip() or None
    return MiniMaxProvider(MiniMaxLLM(api_key=api_key, model=model))


def _create_dashscope_provider() -> DashScopeProvider | None:
    api_key = str(current_app.config.get("DASHSCOPE_API_KEY", "")).strip()
    model = str(current_app.config.get("DASHSCOPE_MODEL", "")).strip()
    if not api_key or not model:
        return None

    try:
        generation_call = _load_dashscope_generation_call()
    except Exception:
        return None
    return DashScopeProvider(api_key=api_key, model=model, generation_call=generation_call)


def _load_dashscope_generation_call() -> Callable[..., object]:
    """延迟导入可选 SDK，避免未安装时影响规则兜底。"""
    from dashscope import Generation

    return Generation.call


def _coerce_request(
    request_or_prompt: LLMRequest | str,
    system_prompt: str | None,
    max_tokens: int,
    temperature: float,
) -> LLMRequest:
    if isinstance(request_or_prompt, LLMRequest):
        return request_or_prompt
    return LLMRequest(
        prompt=request_or_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages


def _minimax_response(raw_response: object, model: str | None, started: float) -> LLMResponse:
    status_code = _as_int(_read_value(raw_response, "status_code"))
    usage = _as_dict(_read_value(raw_response, "usage"))
    if status_code != 200:
        return _failure_response(
            provider_name="minimax",
            model=model,
            warning_code="LLM_PROVIDER_NON_SUCCESS",
            started=started,
            status_code=status_code,
            usage=usage,
        )
    content = _nested_content(raw_response)
    if not content:
        return _failure_response(
            provider_name="minimax",
            model=model,
            warning_code="LLM_OUTPUT_INVALID",
            started=started,
            status_code=status_code,
            usage=usage,
        )
    return LLMResponse(
        text=content,
        provider_name="minimax",
        model=model,
        status_code=status_code,
        latency_ms=_latency_ms(started),
        usage=usage,
        reasoning=_nested_reasoning(raw_response, "reasoning_content"),
    )


def _dashscope_response(raw_response: object, model: str, started: float) -> LLMResponse:
    status_code = _as_int(_read_value(raw_response, "status_code"))
    if status_code != 200:
        return _failure_response(
            provider_name="dashscope",
            model=model,
            warning_code="LLM_PROVIDER_NON_SUCCESS",
            started=started,
            status_code=status_code,
            usage=_as_dict(_read_value(raw_response, "usage")),
        )
    content = _dashscope_message_content(raw_response)
    if content is None:
        return _failure_response(
            provider_name="dashscope",
            model=model,
            warning_code="LLM_OUTPUT_INVALID",
            started=started,
            status_code=status_code,
        )
    return LLMResponse(
        text=content,
        provider_name="dashscope",
        model=model,
        status_code=status_code,
        latency_ms=_latency_ms(started),
        usage=_as_dict(_read_value(raw_response, "usage")),
        reasoning=_nested_reasoning(raw_response, "thinking"),
    )


def _text_response(
    raw_text: object,
    *,
    provider_name: str,
    model: str | None,
    started: float,
) -> LLMResponse:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return _failure_response(
            provider_name=provider_name,
            model=model,
            warning_code="LLM_OUTPUT_INVALID",
            started=started,
        )
    return LLMResponse(
        text=raw_text,
        provider_name=provider_name,
        model=model,
        status_code=200,
        latency_ms=_latency_ms(started),
    )


def _failure_response(
    *,
    provider_name: str,
    model: str | None,
    warning_code: str,
    started: float,
    status_code: int | None = None,
    usage: dict[str, Any] | None = None,
) -> LLMResponse:
    return LLMResponse(
        text=None,
        provider_name=provider_name,
        model=model,
        status_code=status_code,
        warning_code=warning_code,
        latency_ms=_latency_ms(started),
        usage=usage or {},
    )


def _legacy_result(response: LLMResponse) -> str:
    if response.is_success and response.text is not None:
        return response.text
    raise ProviderUnavailableError(response.warning_code or "LLM_PROVIDER_REQUEST_FAILED")


def _nested_content(value: object) -> str | None:
    output = _read_value(value, "output")
    choices = _read_value(output, "choices")
    if choices:
        first = choices[0]
        message = _read_value(first, "message")
        content = _read_value(message, "content")
        if isinstance(content, str) and content.strip():
            return content
    text = _read_value(output, "text")
    if isinstance(text, str) and text.strip():
        return text
    return None


def _nested_reasoning(value: object, field_name: str) -> str | None:
    """从首个 choice 的 message 中提取思维链字段（如 reasoning_content / thinking）。"""
    output = _read_value(value, "output")
    choices = _read_value(output, "choices")
    if not choices:
        return None
    message = _read_value(choices[0], "message")
    reasoning = _read_value(message, field_name)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning
    return None


def _dashscope_message_content(response: object) -> str | None:
    return _nested_content(response)


def _stream_message(value: object) -> object:
    """从流式响应项中提取增量消息对象。"""
    output = _read_value(value, "output")
    choices = _read_value(output, "choices")
    if not choices:
        return None
    return _read_value(choices[0], "message")


def _read_value(value: object, name: str) -> object:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _latency_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _metadata_value(provider: object, name: str) -> str | None:
    value = getattr(provider, name, None)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
