# -*- coding: utf-8 -*-
"""Run budget checks: soft limit (warn) and hard limit (block new LLM calls).

Soft = any budget metric reached 80%; hard = any reached 100%. Hard budget
blocks new LLM planning/analysis but never erases deterministic evidence.
"""
from __future__ import annotations

from datetime import datetime

from app.models.agent_runtime import AgentRun


def budget_status(run: AgentRun) -> dict:
    """Return soft/exhausted flags and per-metric ratios for a run."""
    ratios: dict[str, float] = {}
    current = {
        "llm_calls": run.llm_call_count or 0,
        "tool_calls": run.tool_call_count or 0,
        "total_tokens": run.total_tokens or 0,
        "estimated_cost": float(run.total_cost or 0),
    }
    limits = {
        "llm_calls": run.max_llm_calls,
        "tool_calls": run.max_tool_calls,
        "total_tokens": run.max_total_tokens,
        "estimated_cost": float(run.max_estimated_cost) if run.max_estimated_cost is not None else None,
    }
    if run.max_wall_clock_seconds and run.started_at:
        elapsed = (datetime.utcnow() - run.started_at).total_seconds()
        current["wall_clock_seconds"] = max(0, int(elapsed))
        limits["wall_clock_seconds"] = run.max_wall_clock_seconds

    reached_codes: list[str] = []
    soft = False
    exhausted = False
    for metric, limit in limits.items():
        if limit is None or limit <= 0:
            continue
        value = current.get(metric, 0)
        ratio = value / limit if limit else 0.0
        ratios[metric] = round(ratio, 4)
        if ratio >= 1.0:
            soft = True
            exhausted = True
            reached_codes.append(_code_for(metric, hard=True))
        elif ratio >= 0.8:
            soft = True
            reached_codes.append(_code_for(metric, hard=False))

    return {
        "ratios": ratios,
        "soft": soft,
        "exhausted": exhausted,
        "reached_codes": sorted(set(reached_codes)),
        "current": current,
        "limits": limits,
    }


def _code_for(metric: str, *, hard: bool) -> str:
    if hard:
        return "AGENT_BUDGET_EXHAUSTED"
    return "AGENT_BUDGET_SOFT_LIMIT"
