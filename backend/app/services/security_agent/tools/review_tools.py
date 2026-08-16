# -*- coding: utf-8 -*-
"""run_deep_review 工具（A6）：多文件证据 + RAG 引用 → Observation 落库。

编排（复用既有服务，不复制实现）：
ContextBuilder 组装受限上下文 → select_provider 真实 Provider 调用
（record_invocation 记账）→ parse + validate → ObservationService 落库。
Provider 失败/解析失败 → 工具失败 + warning（不影响 run 其它节点）。
"""
from __future__ import annotations

import logging

from app import db
from app.services.agent_observability import AgentLogger
from app.services.llm.contracts import LLMRequest
from app.services.llm.provider_selector import resolve_provider_max_tokens, select_provider
from app.services.security_agent.context_builder import (
    ContextBuilder,
    DeepReviewContextError,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.feature_flags import AgentFeatureFlags
from app.services.security_agent.harness_v3.deep_review import (
    TargetedContextBuildError,
    TargetedDeepReviewContextBuilder,
    V3DeepReviewInputError,
    V3DeepReviewInputResolver,
)
from app.services.security_agent.llm_invocation import (
    USAGE_SOURCE_PROVIDER_REPORTED,
    record_invocation,
)
from app.services.security_agent.observation_service import ObservationService
from app.services.security_agent.observation_validator import ObservationValidationError
from app.services.security_agent.prompt_templates.deep_review_v1 import (
    PROMPT_TEMPLATE_VERSION,
    build_deep_review_prompt,
    parse_observation,
    prompt_digest,
)
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)
from app.services.security_agent.contracts import EVENT_WARNING_RAISED

logger = logging.getLogger(__name__)

DEEP_REVIEW_OPERATION = "deep_review"
MAX_INPUT_FILES = 8
MAX_FOCUS_CHARS = 500


def build_run_deep_review_handler(events: EventService | None = None):
    events = events or EventService()

    def run_deep_review(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(
                status="failed", summary="任务已取消，未执行深度审查", error_code="AGENT_TOOL_FAILED"
            )
        v3_request = None
        if _uses_v3_harness(ctx.run):
            try:
                v3_request = V3DeepReviewInputResolver().resolve(ctx.run, ctx.input)
                review_context = TargetedDeepReviewContextBuilder().build(
                    ctx.run,
                    v3_request,
                )
            except (V3DeepReviewInputError, TargetedContextBuildError) as exc:
                raise ToolExecutionError(
                    str(exc),
                    warning_code="AGENT_V3_DEEP_REVIEW_INPUT_INVALID",
                ) from exc
        else:
            focus = (ctx.input.get("focus") or "").strip()
            entrypoints = _string_list(ctx.input.get("entrypoints"))
            file_hints = tuple(_string_list(ctx.input.get("file_hints")))[:MAX_INPUT_FILES]
            try:
                review_context = ContextBuilder().build(
                    ctx.run,
                    focus=focus,
                    entrypoints=entrypoints,
                    file_hints=file_hints,
                    max_files=ctx.run.max_deep_review_files,
                )
            except DeepReviewContextError as exc:
                raise ToolExecutionError(str(exc)) from exc

        provider = select_provider(
            user_id=ctx.run.created_by, operation=DEEP_REVIEW_OPERATION
        )
        if provider is None:
            raise ToolExecutionError(
                "未配置 LLM Provider，无法执行 Deep Review",
                warning_code="AGENT_PROVIDER_NOT_CONFIGURED",
            )

        context_text = ContextBuilder().render_context_text(review_context)
        prompt = build_deep_review_prompt(
            focus=review_context.focus,
            context_text=context_text,
            max_tokens=resolve_provider_max_tokens(provider, 1500),
        )
        request = LLMRequest(
            prompt=prompt["user_prompt"],
            system_prompt=prompt["system_prompt"],
            temperature=0.2,
            max_tokens=prompt["max_tokens"],
        )

        from app.services.security_agent.providers.router import AgentProviderRouter

        router = AgentProviderRouter(events)
        candidates = router.candidates(
            user_id=ctx.run.created_by,
            workspace_id=ctx.run.workspace_id,
            operation=DEEP_REVIEW_OPERATION,
        )
        ordered = [provider] + [
            candidate
            for candidate in candidates
            if getattr(candidate, "provider_name", None)
            != getattr(provider, "provider_name", None)
        ]
        response, used, _ = router.generate_with_failover(
            run=ctx.run,
            candidates=ordered,
            request=request,
            trace_id=ctx.trace_id,
            operation=DEEP_REVIEW_OPERATION,
        )
        if response is None:
            _record_failure(ctx, provider, context_text, trace_id=ctx.trace_id)
            raise ToolExecutionError(
                "Deep Review Provider 调用失败", warning_code="AGENT_PROVIDER_UNHEALTHY"
            )
        if not response.is_success:
            _record_failure(ctx, provider, context_text, trace_id=ctx.trace_id)
            raise ToolExecutionError(
                "Deep Review Provider 返回失败",
                warning_code=response.warning_code or "AGENT_PROVIDER_UNHEALTHY",
            )

        _record_success(ctx, used, prompt, response)

        try:
            parsed = parse_observation(response.text)
        except ValueError as exc:
            _raise_invalid_response(ctx, str(exc))
            raise ToolExecutionError(
                "Deep Review 输出无法解析为 Observation",
                warning_code="AGENT_PROVIDER_INVALID_RESPONSE",
            ) from exc

        parsed.setdefault("locations", [])
        parsed.setdefault("proof_gaps", [])

        try:
            parsed["citations"] = _select_background_citations(
                parsed,
                review_context,
            )
            observation = ObservationService(events).create(
                ctx.run,
                parsed,
                trace_id=ctx.trace_id,
                evidence_scope=review_context.files,
            )
        except ObservationValidationError as exc:
            _raise_invalid_response(ctx, str(exc))
            raise ToolExecutionError(
                f"Observation 校验未通过：{exc}",
                warning_code="AGENT_PROVIDER_INVALID_RESPONSE",
            ) from exc

        if v3_request is not None:
            _record_v3_hypothesis_progress(v3_request.hypothesis, ctx)

        return ToolResult(
            status="succeeded",
            summary=(
                f"Deep Review 完成：{observation.title}（confidence={observation.confidence}，"
                f"{len(observation.locations)} 个位置，{len(observation.citations)} 条引用）"
            ),
            metrics={
                "observation_id": observation.id,
                "title": observation.title,
                "confidence": observation.confidence,
                "cwe_id": observation.cwe_id,
                "location_count": len(observation.locations),
                "citation_count": len(observation.citations),
                "proof_gap_count": len(parsed["proof_gaps"]),
                "injected_docs": list(review_context.injected_doc_ids),
                "hypothesis_id": v3_request.hypothesis_id if v3_request is not None else None,
                "review_kind": v3_request.review_kind if v3_request is not None else None,
            },
        )

    return run_deep_review


# ------------------------------------------------------------------ helpers


def _uses_v3_harness(run) -> bool:
    """只让已灰度的 Hybrid / Deep Audit 使用假设绑定的 Deep Review。"""
    mode = getattr(getattr(run, "mode", None), "value", getattr(run, "mode", None))
    flags = AgentFeatureFlags().for_run(run)
    return bool(flags.harness_v3) and mode in {"hybrid", "deep_audit"}


def _record_v3_hypothesis_progress(hypothesis, ctx: ToolExecutionContext) -> None:
    """仅记录结构化工具关联；源码与 Prompt 不进入假设持久化记录。"""
    status = getattr(getattr(hypothesis, "status", None), "value", hypothesis.status)
    if status == "queued":
        hypothesis.status = "active"
    hypothesis.execution_attempt_count = (hypothesis.execution_attempt_count or 0) + 1
    tool_call_id = getattr(getattr(ctx, "tool_call", None), "id", None)
    if isinstance(tool_call_id, int) and tool_call_id > 0:
        hypothesis.related_tool_call_id = tool_call_id
    db.session.commit()


def _string_list(value) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _select_background_citations(parsed: dict, review_context) -> list[dict]:
    """只持久化模型从当前 Context Pack 显式选中的背景资料。"""
    requested_ids = parsed.pop("knowledge_reference_ids", [])
    if requested_ids is None:
        requested_ids = []
    if not isinstance(requested_ids, list):
        raise ObservationValidationError("knowledge_reference_ids 必须是数组")

    allowed = {
        citation.document_id: citation
        for citation in review_context.citations
        if citation.document_id
    }
    selected: list[dict] = []
    seen: set[str] = set()
    for raw_document_id in requested_ids:
        document_id = str(raw_document_id or "").strip()
        if not document_id or document_id in seen:
            continue
        citation = allowed.get(document_id)
        if citation is None:
            raise ObservationValidationError(
                f"knowledge_reference_ids 包含未授权文档：{document_id[:120]}"
            )
        seen.add(document_id)
        selected.append(
            {
                "source_type": "rag_background",
                "document_id": citation.document_id,
                "document_title": citation.document_title,
                "trust_score": citation.trust_score,
                "injection_flags": list(citation.injection_flags),
                "content_digest": citation.content_digest,
                "quote_preview": citation.quote_preview,
            }
        )
    return selected


def _record_success(ctx, provider, prompt: dict, response) -> None:
    record_invocation(
        ctx.run,
        provider=provider,
        operation=DEEP_REVIEW_OPERATION,
        status="success",
        input_tokens=int((response.usage or {}).get("prompt_tokens") or 0),
        output_tokens=int((response.usage or {}).get("completion_tokens") or 0),
        cached_input_tokens=int((response.usage or {}).get("cached_tokens") or 0),
        reasoning_tokens=int((response.usage or {}).get("reasoning_tokens") or 0),
        total_tokens=int((response.usage or {}).get("total_tokens") or 0),
        usage_source=USAGE_SOURCE_PROVIDER_REPORTED if response.usage else "estimated",
        latency_ms=response.latency_ms,
        input_digest=prompt_digest(prompt["user_prompt"]),
        output_digest=prompt_digest(response.text) if response.text else None,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        step_execution_id=ctx.step_execution.id if ctx.step_execution else None,
    )
    db.session.commit()
    AgentLogger().llm_event(
        "llm.completed",
        ctx.run,
        operation=DEEP_REVIEW_OPERATION,
        provider=getattr(provider, "provider_name", "unknown"),
        model=getattr(provider, "model", None),
        status="success",
        total_tokens=int((response.usage or {}).get("total_tokens") or 0),
        input_digest=prompt_digest(prompt["user_prompt"]),
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        trace_id=ctx.trace_id,
    )


def _record_failure(ctx, provider, context_text: str, *, trace_id: str | None) -> None:
    record_invocation(
        ctx.run,
        provider=provider,
        operation=DEEP_REVIEW_OPERATION,
        status="failed",
        warning_code="LLM_PROVIDER_REQUEST_FAILED",
        input_digest=prompt_digest(context_text),
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        step_execution_id=ctx.step_execution.id if ctx.step_execution else None,
    )
    db.session.commit()


def _raise_invalid_response(ctx, reason: str) -> None:
    events = EventService()
    events.emit(
        ctx.run,
        EVENT_WARNING_RAISED,
        {"warning_codes": ["AGENT_PROVIDER_INVALID_RESPONSE"], "reason": reason[:200]},
        trace_id=ctx.trace_id,
    )
