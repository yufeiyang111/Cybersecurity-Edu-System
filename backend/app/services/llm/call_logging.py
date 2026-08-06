"""Safe observation wrapper for LLM Provider calls."""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Iterator

from flask import current_app, has_app_context, has_request_context
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.llm import LLMCallLog
from app.services.observability import get_request_id

from .contracts import LLMRequest, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)


class LoggedLLMProvider:
    """Delegate Provider calls and persist only normalized metadata."""

    def __init__(self, provider: object, *, user_id: int | None, operation: str) -> None:
        self._provider = provider
        self.user_id = user_id
        self.operation = operation
        self.provider_config_id = getattr(provider, "provider_config_id", None)

    def __getattr__(self, name: str):
        return getattr(self._provider, name)

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = perf_counter()
        try:
            response = self._provider.generate(request)
            logger.info(
                "LoggedLLMProvider.generate raw response (provider=%s, operation=%s, "
                "is_success=%s, warning_code=%s, text=%r, status_code=%s)",
                getattr(self._provider, "provider_name", "?"),
                self.operation,
                response.is_success if isinstance(response, LLMResponse) else "NOT_LLMRESPONSE",
                response.warning_code if isinstance(response, LLMResponse) else "N/A",
                response.text[:50] if isinstance(response, LLMResponse) and response.text else None,
                response.status_code if isinstance(response, LLMResponse) else "N/A",
            )
        except Exception as exc:
            logger.exception(
                "LoggedLLMProvider.generate caught exception (provider=%s, operation=%s): %s",
                getattr(self._provider, "provider_name", "?"),
                self.operation,
                exc,
            )
            _write_log(
                self,
                status="failed",
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                started=started,
                streaming=False,
            )
            raise
        if isinstance(response, LLMResponse):
            _write_log(
                self,
                status=_response_status(response),
                warning_code=response.warning_code,
                started=started,
                streaming=False,
                response=response,
            )
        else:
            _write_log(
                self,
                status="invalid_response",
                warning_code="LLM_PROVIDER_RESPONSE_INVALID",
                started=started,
                streaming=False,
            )
        return response

    def generate_stream(self, request: LLMRequest) -> Iterator[LLMStreamChunk]:
        started = perf_counter()
        warning_code = None
        first_token_latency_ms = None
        output_tokens = 0
        usage = {}
        try:
            stream = self._provider.generate_stream(request)
            for chunk in stream:
                if not isinstance(chunk, LLMStreamChunk):
                    warning_code = "LLM_PROVIDER_RESPONSE_INVALID"
                    yield LLMStreamChunk(finished=True, warning_code=warning_code)
                    return
                if (chunk.delta or chunk.reasoning_delta) and first_token_latency_ms is None:
                    first_token_latency_ms = _elapsed_ms(started)
                if chunk.delta:
                    output_tokens += _estimate_tokens(chunk.delta)
                if chunk.warning_code:
                    warning_code = chunk.warning_code
                if isinstance(chunk.usage, dict) and chunk.usage:
                    usage = chunk.usage
                yield chunk
                if chunk.finished:
                    break
        except Exception:
            warning_code = "LLM_PROVIDER_REQUEST_FAILED"
            yield LLMStreamChunk(finished=True, warning_code=warning_code)
        finally:
            _write_log(
                self,
                status=_stream_status(warning_code, output_tokens),
                warning_code=warning_code,
                started=started,
                streaming=True,
                first_token_latency_ms=first_token_latency_ms,
                output_tokens=output_tokens,
                usage=usage,
            )


def observe_provider(provider: object, *, user_id: int | None, operation: str) -> LoggedLLMProvider:
    return LoggedLLMProvider(provider, user_id=user_id, operation=operation)


def _write_log(
    provider: LoggedLLMProvider,
    *,
    status: str,
    warning_code: str | None,
    started: float,
    streaming: bool,
    response: LLMResponse | None = None,
    first_token_latency_ms: int | None = None,
    output_tokens: int = 0,
    usage: dict | None = None,
) -> None:
    if provider.user_id is None or not has_app_context():
        return
    usage = response.usage if response and isinstance(response.usage, dict) else (usage or {})
    input_tokens = _usage_int(usage, "input_tokens", "prompt_tokens")
    response_output_tokens = _usage_int(usage, "output_tokens", "completion_tokens")
    output_tokens = response_output_tokens or output_tokens
    cached_input_tokens = _usage_int(usage, "cached_input_tokens", "prompt_tokens_details.cached_tokens")
    reasoning_tokens = _usage_int(usage, "reasoning_tokens", "completion_tokens_details.reasoning_tokens")
    total_tokens = _usage_int(usage, "total_tokens") or input_tokens + output_tokens
    try:
        db.session.add(
            LLMCallLog(
                user_id=provider.user_id,
                provider_config_id=provider.provider_config_id,
                provider_name=str(getattr(provider, "provider_name", "unknown"))[:128],
                model=str(getattr(provider, "model", "") or "")[:200] or None,
                operation=str(provider.operation or "unknown")[:64],
                status=status,
                warning_code=warning_code,
                request_id=get_request_id() if has_request_context() else None,
                streaming=streaming,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=cached_input_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=total_tokens,
                latency_ms=_elapsed_ms(started),
                first_token_latency_ms=first_token_latency_ms,
            )
        )
        db.session.flush()
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "LLM call metadata could not be persisted (error_type=%s)",
            type(exc).__name__,
        )


def _response_status(response: LLMResponse) -> str:
    if response.is_success:
        return "success"
    if response.warning_code == "LLM_PROVIDER_TIMEOUT":
        return "timeout"
    if response.warning_code in {"LLM_OUTPUT_INVALID", "LLM_PROVIDER_RESPONSE_INVALID"}:
        return "invalid_response"
    return "failed"


def _stream_status(warning_code: str | None, output_tokens: int) -> str:
    if warning_code == "LLM_PROVIDER_TIMEOUT":
        return "timeout"
    if warning_code:
        return "invalid_response" if warning_code == "LLM_OUTPUT_INVALID" else "failed"
    return "success" if output_tokens > 0 else "invalid_response"


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _estimate_tokens(value: str) -> int:
    return max(1, len(value.strip()) // 4) if value.strip() else 0


def _usage_int(usage: dict, *keys: str) -> int:
    for key in keys:
        current = usage
        for part in key.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if isinstance(current, int) and not isinstance(current, bool) and current >= 0:
            return current
    return 0
