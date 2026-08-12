# -*- coding: utf-8 -*-
"""AgentModelGateway（T04，spec §7）：Provider 路由、Tool Calling 适配与标准化。

- next_turn：能力协商 → 原生 Tool Calling 或严格 JSON Fallback → 调用记录；
- stream_turn：流式事件标准化透传（缺 completed 时补齐）；
- failover：候选链中首个失败（warning_code 非空）自动切换，并发出
  strategy.provider_switched 事件；切换后保留完整标准化上下文。
- 本模块不执行业务授权与工具执行（T05/T08 负责），不记录 Prompt 原文。
"""
from __future__ import annotations

import dataclasses
import hashlib
import logging
from collections.abc import Iterator

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.model.action_parser import (
    ActionParseError,
    parse_action_envelope,
    repair_prompt,
)
from app.services.security_agent.model.context_renderer import render_fallback_prompt
from app.services.security_agent.model.contracts import (
    AgentModelRequest,
    AgentModelResponse,
    AgentModelStreamEvent,
    AgentStreamEventType,
    ProviderCapabilities,
)
from app.services.security_agent.timeline.contracts import (
    EVENT_STRATEGY_PROVIDER_SWITCHED,
)
from app.services.security_agent.timeline.event_writer import EventWriter

logger = logging.getLogger(__name__)

_MAX_FALLBACK_REPAIRS = 1
_DEFAULT_OPERATION = "agent_model"


def merge_tool_call_arguments(deltas: list[tuple[str, str]]) -> dict[str, str]:
    """按 provider call ID 合并并列 Tool Call 的 arguments delta，绝不串线。"""
    merged: dict[str, str] = {}
    for call_id, delta in deltas:
        merged[call_id] = merged.get(call_id, "") + delta
    return merged


class AgentModelGateway:
    def __init__(self, writer: EventWriter | None = None) -> None:
        self._writer = writer or EventWriter()

    # ---------------------------------------------------------------- public

    def capabilities(self, provider: object) -> ProviderCapabilities:
        """能力协商：provider 声明 agent_capabilities() 则采用，否则全部关闭。"""
        probe = getattr(provider, "agent_capabilities", None)
        if callable(probe):
            return probe()
        return ProviderCapabilities()

    def next_turn(
        self,
        request: AgentModelRequest,
        *,
        provider: object,
        run: AgentRun | None = None,
        candidates: tuple[object, ...] = (),
        trace_id: str | None = None,
        operation: str = _DEFAULT_OPERATION,
    ) -> AgentModelResponse:
        ordered = (provider,) + tuple(
            candidate
            for candidate in candidates
            if candidate is not provider
        )
        failures: list[str] = []
        for index, candidate in enumerate(ordered):
            caps = self.capabilities(candidate)
            try:
                if caps.supports_native_tools:
                    response = candidate.generate_agent(request)
                else:
                    response = self._fallback_generate(candidate, request)
            except ActionParseError as exc:
                failures.append(str(exc))
                continue
            if response.warning_code and index < len(ordered) - 1:
                failures.append(response.warning_code)
                continue
            if index > 0 and run is not None:
                self._emit_provider_switched(run, ordered[0], candidate, trace_id)
            if run is not None:
                self._record_invocation(
                    run, candidate, request, response, operation, trace_id
                )
            return response
        last = ordered[-1] if ordered else provider
        return AgentModelResponse(
            content=None,
            tool_calls=(),
            finish_reason=None,
            provider_name=getattr(last, "provider_name", "unknown"),
            model=getattr(last, "model", None),
            warning_code=failures[-1] if failures else "LLM_PROVIDER_REQUEST_FAILED",
        )

    def stream_turn(
        self,
        request: AgentModelRequest,
        *,
        provider: object,
        run: AgentRun | None = None,
        trace_id: str | None = None,
        operation: str = _DEFAULT_OPERATION,
    ) -> Iterator[AgentModelStreamEvent]:
        caps = self.capabilities(provider)
        streamer = getattr(provider, "generate_agent_stream", None)
        if caps.supports_streaming and callable(streamer):
            yield from self.normalize_stream(streamer(request))
            return
        response = self.next_turn(
            request,
            provider=provider,
            run=run,
            trace_id=trace_id,
            operation=operation,
        )
        if response.content:
            yield AgentModelStreamEvent(
                event_type=AgentStreamEventType.OUTPUT_TEXT_DELTA.value,
                item_id="assistant",
                delta=response.content,
            )
        yield AgentModelStreamEvent(
            event_type=(
                AgentStreamEventType.FAILED.value
                if response.warning_code
                else AgentStreamEventType.COMPLETED.value
            ),
            payload={"warning_code": response.warning_code}
            if response.warning_code
            else {},
        )

    def normalize_stream(
        self, events: Iterator[AgentModelStreamEvent] | list[AgentModelStreamEvent]
    ) -> Iterator[AgentModelStreamEvent]:
        """标准化流事件：校验类型、透传、缺 completed/failed 时补齐。"""
        seen_terminal = False
        for event in events:
            if event.event_type in {
                AgentStreamEventType.COMPLETED.value,
                AgentStreamEventType.FAILED.value,
            }:
                seen_terminal = True
            yield event
        if not seen_terminal:
            yield AgentModelStreamEvent(event_type=AgentStreamEventType.COMPLETED.value)

    # ---------------------------------------------------------------- fallback

    def _fallback_generate(
        self, provider: object, request: AgentModelRequest
    ) -> AgentModelResponse:
        from app.services.llm.contracts import LLMRequest

        base_prompt = render_fallback_prompt(request)
        response = provider.generate(
            LLMRequest(
                prompt=base_prompt,
                system_prompt="只输出符合 Action Envelope schema 的 JSON 对象。",
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        )
        if response.warning_code or not response.text:
            return AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason=None,
                provider_name=getattr(provider, "provider_name", "unknown"),
                model=getattr(provider, "model", None),
                warning_code=response.warning_code or "LLM_OUTPUT_INVALID",
            )
        try:
            return self._tag_provider(
                parse_action_envelope(response.text), provider
            )
        except ActionParseError as exc:
            return self._repair_once(provider, request, base_prompt, str(exc))

    def _repair_once(
        self,
        provider: object,
        request: AgentModelRequest,
        base_prompt: str,
        failure_reason: str,
    ) -> AgentModelResponse:
        """一次受控修复；再次失败返回显式错误码，不猜不改写。"""
        from app.services.llm.contracts import LLMRequest

        repair = LLMRequest(
            prompt=base_prompt + "\n\n" + repair_prompt(failure_reason),
            system_prompt="只输出符合 Action Envelope schema 的 JSON 对象。",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        second = provider.generate(repair)
        if second.warning_code or not second.text:
            return AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason=None,
                provider_name=getattr(provider, "provider_name", "unknown"),
                model=getattr(provider, "model", None),
                warning_code=second.warning_code or "LLM_OUTPUT_INVALID",
            )
        try:
            return self._tag_provider(parse_action_envelope(second.text), provider)
        except ActionParseError as exc:
            return AgentModelResponse(
                content=None,
                tool_calls=(),
                finish_reason=None,
                provider_name=getattr(provider, "provider_name", "unknown"),
                model=getattr(provider, "model", None),
                warning_code="LLM_OUTPUT_INVALID",
            )

    @staticmethod
    def _tag_provider(
        response: AgentModelResponse, provider: object
    ) -> AgentModelResponse:
        return dataclasses.replace(
            response,
            provider_name=getattr(provider, "provider_name", "fallback"),
            model=getattr(provider, "model", None),
        )

    # ---------------------------------------------------------------- record/event

    def _record_invocation(
        self,
        run: AgentRun,
        provider: object,
        request: AgentModelRequest,
        response: AgentModelResponse,
        operation: str,
        trace_id: str | None,
    ) -> None:
        from app.services.security_agent.llm_invocation import (
            USAGE_SOURCE_PROVIDER_REPORTED,
            record_invocation,
        )

        usage = response.usage or {}
        record_invocation(
            run,
            provider=provider,
            operation=operation,
            status="success" if not response.warning_code else "failed",
            warning_code=response.warning_code,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED if usage else "estimated",
            input_digest=_sha256(_request_digest_text(request)),
            output_digest=_sha256(
                response.content or str(response.tool_calls)
            ) if (response.content or response.tool_calls) else None,
        )
        db.session.commit()

    def _emit_provider_switched(
        self,
        run: AgentRun,
        from_provider: object,
        to_provider: object,
        trace_id: str | None,
    ) -> AgentEvent:
        return self._writer.emit(
            run,
            event_type=EVENT_STRATEGY_PROVIDER_SWITCHED,
            payload={
                "from_provider": getattr(from_provider, "provider_name", "unknown"),
                "to_provider": getattr(to_provider, "provider_name", "unknown"),
            },
            trace_id=trace_id,
        )


def _request_digest_text(request: AgentModelRequest) -> str:
    parts = [f"messages={len(request.messages)}", f"tools={len(request.tools)}"]
    for message in request.messages:
        parts.append(
            f"{message.role}:{len(message.content or '')}:"
            f"{','.join(call.name for call in message.tool_calls)}"
        )
    return "|".join(parts)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
