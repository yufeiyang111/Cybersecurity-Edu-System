# -*- coding: utf-8 -*-
"""Harness V3 Deep Review 的 Provider 调用适配。

只在 Provider 能真实流式返回 reasoning 时即时转发 delta；正常文本仍沿用
既有 Provider Router 的 failover。原始 reasoning 不进入返回对象或持久化链路。
"""
from __future__ import annotations

from time import perf_counter

from app.services.llm.contracts import LLMResponse
from app.services.security_agent.harness_v3.raw_reasoning import (
    ProviderRawReasoningRelay,
    get_provider_raw_reasoning_relay,
)


class DeepReviewProviderInvoker:
    """保持 Deep Review 解析契约，同时为 V3 提供可选的瞬时 raw 流。"""

    def __init__(self, *, relay: ProviderRawReasoningRelay | None = None) -> None:
        self._relay = relay or get_provider_raw_reasoning_relay()

    def invoke(
        self,
        *,
        run,
        candidates: list[object],
        request,
        router,
        trace_id: str | None,
        operation: str,
    ) -> tuple[LLMResponse | None, object | None]:
        """优先消费第一条可用真实流；失败时回退已有 Router 的普通 failover。"""
        stream_provider = self._first_streaming_candidate(run, candidates)
        if stream_provider is not None:
            streamed = self._consume_stream(run, stream_provider, request)
            if streamed.is_success:
                return streamed, stream_provider

        response, used, _ = router.generate_with_failover(
            run=run,
            candidates=candidates,
            request=request,
            trace_id=trace_id,
            operation=operation,
        )
        if response is not None and response.is_success:
            reasoning = getattr(response, "reasoning", None)
            if isinstance(reasoning, str) and reasoning:
                self._relay.publish(run, run.created_by, reasoning)
        return response, used

    def _first_streaming_candidate(self, run, candidates: list[object]) -> object | None:
        if not self._relay.can_stream(run, run.created_by):
            return None
        for provider in candidates:
            if callable(getattr(provider, "generate_stream", None)):
                return provider
        return None

    def _consume_stream(self, run, provider: object, request) -> LLMResponse:
        """累计可见 JSON 文本，Provider raw reasoning 仅逐块发布到瞬时中继。"""
        started = perf_counter()
        text_parts: list[str] = []
        usage: dict = {}
        warning_code: str | None = None
        try:
            for chunk in provider.generate_stream(request):
                reasoning_delta = getattr(chunk, "reasoning_delta", "")
                if isinstance(reasoning_delta, str) and reasoning_delta:
                    self._relay.publish(run, run.created_by, reasoning_delta)
                visible_delta = getattr(chunk, "delta", "")
                if isinstance(visible_delta, str) and visible_delta:
                    text_parts.append(visible_delta)
                chunk_usage = getattr(chunk, "usage", None)
                if isinstance(chunk_usage, dict) and chunk_usage:
                    usage = dict(chunk_usage)
                current_warning = getattr(chunk, "warning_code", None)
                if isinstance(current_warning, str) and current_warning:
                    warning_code = current_warning
                    break
                if bool(getattr(chunk, "finished", False)):
                    break
        except Exception:
            warning_code = "LLM_PROVIDER_REQUEST_FAILED"

        text = "".join(text_parts).strip() or None
        if warning_code is None and text is None:
            warning_code = "LLM_OUTPUT_INVALID"
        return LLMResponse(
            text=text,
            provider_name=str(getattr(provider, "provider_name", "unknown")),
            model=getattr(provider, "model", None),
            status_code=200 if warning_code is None else None,
            warning_code=warning_code,
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
            usage=usage,
            reasoning=None,
        )
