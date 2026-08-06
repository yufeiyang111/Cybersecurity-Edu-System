# -*- coding: utf-8 -*-
"""Agent-run LLM invocation persistence and run-level usage/cost accumulation.

Shared by the planner and the llm_analysis service so every LLM call made on
behalf of a run is audited once: prompt/output are never stored, only digests.
"""
from __future__ import annotations

from app import db
from app.models.agent_llm import LLMInvocation
from app.models.agent_runtime import AgentRun
from app.services.llm.pricing import calculate_cost

USAGE_SOURCE_PROVIDER_REPORTED = "provider_reported"
USAGE_SOURCE_ESTIMATED = "estimated"
USAGE_SOURCE_UNKNOWN = "unknown"


def record_invocation(
    run: AgentRun,
    *,
    provider: object,
    operation: str,
    status: str,
    warning_code: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    cache_creation_tokens: int = 0,
    reasoning_tokens: int = 0,
    total_tokens: int = 0,
    usage_source: str = USAGE_SOURCE_UNKNOWN,
    latency_ms: int | None = None,
    first_token_latency_ms: int | None = None,
    prompt_template_version: str | None = None,
    input_digest: str | None = None,
    output_digest: str | None = None,
    step_execution_id: int | None = None,
    provider_cache_hit: bool = False,
) -> LLMInvocation:
    """Persist one invocation and accumulate token/cost onto the run row."""
    provider_name = str(getattr(provider, "provider_name", "unknown"))[:128]
    model = getattr(provider, "model", None)
    model_version = getattr(provider, "model_version", None)
    provider_config_id = getattr(provider, "provider_config_id", None)

    cost = calculate_cost(
        provider_name=provider_name,
        model=model,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_creation_tokens=cache_creation_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
    )
    invocation = LLMInvocation(
        run_id=run.id,
        step_execution_id=step_execution_id,
        workspace_id=run.workspace_id,
        user_id=run.created_by,
        provider_config_id=provider_config_id,
        provider_name=provider_name,
        model=str(model)[:200] if model else None,
        model_version=str(model_version)[:64] if model_version else None,
        operation=str(operation)[:64],
        prompt_template_version=prompt_template_version,
        input_digest=input_digest,
        output_digest=output_digest,
        status=status,
        warning_code=warning_code,
        latency_ms=latency_ms,
        first_token_latency_ms=first_token_latency_ms,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_creation_tokens=cache_creation_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        usage_source=usage_source,
        currency=cost["currency"],
        input_cost=cost["input_cost"],
        cached_input_cost=cost["cached_input_cost"],
        output_cost=cost["output_cost"],
        reasoning_cost=cost["reasoning_cost"],
        total_cost=cost["total_cost"],
        pricing_version=cost["pricing_version"],
        provider_cache_hit=provider_cache_hit,
    )
    db.session.add(invocation)

    run.llm_call_count = (run.llm_call_count or 0) + 1
    run.input_tokens = (run.input_tokens or 0) + input_tokens
    run.output_tokens = (run.output_tokens or 0) + output_tokens
    run.cached_input_tokens = (run.cached_input_tokens or 0) + cached_input_tokens
    run.reasoning_tokens = (run.reasoning_tokens or 0) + reasoning_tokens
    run.total_tokens = (run.total_tokens or 0) + total_tokens
    run.total_cost = float(run.total_cost or 0) + cost["total_cost"]
    run.currency = cost["currency"]
    return invocation


def list_invocations(run_id: int, *, limit: int = 50) -> list[LLMInvocation]:
    return (
        LLMInvocation.query.filter_by(run_id=run_id)
        .order_by(LLMInvocation.id.desc())
        .limit(limit)
        .all()
    )
