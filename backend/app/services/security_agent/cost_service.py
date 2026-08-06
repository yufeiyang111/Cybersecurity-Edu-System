# -*- coding: utf-8 -*-
"""Agent-run cost queries: per-run invocation list and honest cost summary.

Costs are explicit about their source: provider_reported, estimated (built-in
catalog) or unknown (no price entry); unknown is never shown as a confident 0.
"""
from __future__ import annotations

from app.models.agent_runtime import AgentRun
from app.services.security_agent.llm_invocation import list_invocations


def run_costs(run: AgentRun, *, limit: int = 100) -> dict:
    """Return the cost payload for one run (invocations + summary)."""
    invocations = list_invocations(run.id, limit=limit)
    return {
        "run_id": run.id,
        "summary": _summary(run, invocations),
        "invocations": [invocation.to_dict() for invocation in reversed(invocations)],
    }


def _summary(run: AgentRun, invocations) -> dict:
    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    reasoning_tokens = 0
    total_tokens = 0
    total_cost = 0.0
    usage_sources = {"provider_reported": 0, "estimated": 0, "unknown": 0}
    price_known_invocations = 0
    for invocation in invocations:
        input_tokens += invocation.input_tokens or 0
        output_tokens += invocation.output_tokens or 0
        cached_input_tokens += invocation.cached_input_tokens or 0
        reasoning_tokens += invocation.reasoning_tokens or 0
        total_tokens += invocation.total_tokens or 0
        total_cost += float(invocation.total_cost or 0)
        source = invocation.usage_source or "unknown"
        usage_sources[source] = usage_sources.get(source, 0) + 1
        if invocation.pricing_version:
            price_known_invocations += 1
    return {
        "calls": len(invocations),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "currency": run.currency or "USD",
        "usage_sources": usage_sources,
        "cost_known": price_known_invocations > 0,
        "cost_source": _cost_source(price_known_invocations, len(invocations)),
    }


def _cost_source(price_known: int, total: int) -> str:
    if total == 0:
        return "none"
    if price_known == total:
        return "estimated"
    if price_known == 0:
        return "unknown"
    return "mixed"
