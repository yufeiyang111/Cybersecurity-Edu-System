"""Shared contracts for the security agent domain (event types, warning codes)."""
from __future__ import annotations

AGENT_EVENT_SCHEMA_VERSION = 1

EVENT_RUN_CREATED = "run.created"
EVENT_RUN_STATE_CHANGED = "run.state_changed"
EVENT_RUN_PAUSED = "run.paused"
EVENT_RUN_RESUMED = "run.resumed"
EVENT_RUN_COMPLETED = "run.completed"
EVENT_PLAN_CREATED = "plan.created"
EVENT_PLAN_VALIDATED = "plan.validated"
EVENT_PLAN_REPLANNED = "plan.replanned"
EVENT_STEP_STARTED = "step.started"
EVENT_STEP_COMPLETED = "step.completed"
EVENT_STEP_FAILED = "step.failed"
EVENT_TOOL_STARTED = "tool.started"
EVENT_TOOL_PROGRESS = "tool.progress"
EVENT_TOOL_COMPLETED = "tool.completed"
EVENT_TOOL_FAILED = "tool.failed"
EVENT_LLM_STARTED = "llm.started"
EVENT_LLM_USAGE = "llm.usage"
EVENT_LLM_COMPLETED = "llm.completed"
EVENT_LLM_FAILED = "llm.failed"
EVENT_LLM_REASONING_DELTA = "llm.reasoning_delta"

# llm.reasoning_delta is a PASS-THROUGH event for clients: it is emitted in
# real time and persisted (events.emit writes every event so SSE replay stays
# gapless), but client reducers only accumulate the delta and never show it in
# the event history list; it is never written to call logs or audit.
PASS_THROUGH_EVENT_TYPES = frozenset({EVENT_LLM_REASONING_DELTA})
EVENT_STRATEGY_SWITCHED = "strategy.switched"
EVENT_DECISION_RECORDED = "decision.recorded"
EVENT_APPROVAL_REQUESTED = "approval.requested"
EVENT_APPROVAL_RESOLVED = "approval.resolved"
EVENT_OBSERVATION_CREATED = "observation.created"
EVENT_BUDGET_UPDATED = "budget.updated"
EVENT_WARNING_RAISED = "warning.raised"
EVENT_HEARTBEAT = "heartbeat"

AGENT_EVENT_TYPES = frozenset(
    {
        EVENT_RUN_CREATED,
        EVENT_RUN_STATE_CHANGED,
        EVENT_RUN_PAUSED,
        EVENT_RUN_RESUMED,
        EVENT_RUN_COMPLETED,
        EVENT_PLAN_CREATED,
        EVENT_PLAN_VALIDATED,
        EVENT_PLAN_REPLANNED,
        EVENT_STEP_STARTED,
        EVENT_STEP_COMPLETED,
        EVENT_STEP_FAILED,
        EVENT_TOOL_STARTED,
        EVENT_TOOL_PROGRESS,
        EVENT_TOOL_COMPLETED,
        EVENT_TOOL_FAILED,
        EVENT_LLM_STARTED,
        EVENT_LLM_USAGE,
        EVENT_LLM_COMPLETED,
        EVENT_LLM_FAILED,
        EVENT_LLM_REASONING_DELTA,
        EVENT_STRATEGY_SWITCHED,
        EVENT_DECISION_RECORDED,
        EVENT_APPROVAL_REQUESTED,
        EVENT_APPROVAL_RESOLVED,
        EVENT_OBSERVATION_CREATED,
        EVENT_BUDGET_UPDATED,
        EVENT_WARNING_RAISED,
        EVENT_HEARTBEAT,
    }
)

AGENT_WARNING_CODES = frozenset(
    {
        "AGENT_PROVIDER_NOT_CONFIGURED",
        "AGENT_PROVIDER_UNHEALTHY",
        "AGENT_PROVIDER_TIMEOUT",
        "AGENT_PROVIDER_RATE_LIMITED",
        "AGENT_PROVIDER_INVALID_RESPONSE",
        "AGENT_PLAN_INVALID",
        "AGENT_PLAN_CYCLE_DETECTED",
        "AGENT_PLAN_REPAIR_EXHAUSTED",
        "AGENT_TOOL_NOT_ALLOWED",
        "AGENT_TOOL_TIMEOUT",
        "AGENT_TOOL_FAILED",
        "AGENT_TOOL_RETRY_EXHAUSTED",
        "AGENT_BUDGET_SOFT_LIMIT",
        "AGENT_BUDGET_EXHAUSTED",
        "AGENT_APPROVAL_REQUIRED",
        "AGENT_APPROVAL_REJECTED",
        "AGENT_APPROVAL_EXPIRED",
        "AGENT_LEASE_EXPIRED",
        "AGENT_SSE_REPLAY_GAP",
        "AGENT_VECTOR_FALLBACK",
        "AGENT_CITATION_GAP",
        "AGENT_CONTEXT_LIMITED",
        "AGENT_REPLAN_LIMIT_REACHED",
        "AGENT_PARTIAL_RESULT",
    }
)

AGENT_RUN_MODES = frozenset({"baseline", "hybrid", "deep_audit"})

# Stable planner source labels; rule-based policy plans must never masquerade as LLM output.
PLANNER_RULE_BASED = "rule_based_policy"
PLANNER_LLM_LIVE = "llm_live"
