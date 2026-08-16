# -*- coding: utf-8 -*-
"""CompletionEvaluator：统一 Agent Run 完成、阻塞和警告判定。"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNodeStatus,
    AgentRun,
    AgentRunStatus,
)
from app.services.security_agent.budget import budget_status
from app.services.security_agent.planning.completion_criteria import (
    CompletionCriteria,
)

_FAILED_STATUSES = frozenset({AgentPlanNodeStatus.FAILED.value})
_MISSING_STATUSES = frozenset(
    {
        AgentPlanNodeStatus.PENDING.value,
        AgentPlanNodeStatus.READY.value,
        AgentPlanNodeStatus.RUNNING.value,
        AgentPlanNodeStatus.BLOCKED.value,
    }
)
_LIMIT_WARNING_CODES = frozenset(
    {
        "AGENT_ITERATION_LIMIT_REACHED",
        "AGENT_BUDGET_EXHAUSTED",
    }
)


@dataclass(frozen=True)
class CompletionVerdict:
    accepted: bool
    terminal_status: str
    missing_requirements: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    completion_reason: str = ""


class CompletionEvaluator:
    def evaluate(
        self,
        run: AgentRun,
        plan: AgentPlan | None,
        *,
        evidence: dict | None = None,
        model_final: str | None = None,
        limit_code: str | None = None,
    ) -> CompletionVerdict:
        """按模式、计划、证据和硬限制判定终态。

        ``partial`` 只保留给历史调用方的兼容路径；新产生的硬限制结果使用：
        - 有可用结果但触发限制：``completed_with_warnings``；
        - 结果不可安全交付、等待更多证据或需要人工介入：``blocked``。
        """
        status = _status_value(run.status)
        if status == AgentRunStatus.CANCELED.value:
            return CompletionVerdict(
                accepted=False,
                terminal_status=AgentRunStatus.CANCELED.value,
                completion_reason="用户取消",
            )

        criteria = CompletionCriteria.for_mode(_status_value(run.mode))
        missing: list[str] = []
        failed: list[str] = []
        node_statuses = {}
        if plan is not None:
            node_statuses = {
                node.node_key: _status_value(node.status)
                for node in plan.nodes
            }
        for key in criteria.mandatory_node_keys:
            node_status = node_statuses.get(key)
            if node_status in _FAILED_STATUSES:
                failed.append(key)
            elif node_status in _MISSING_STATUSES or node_status is None:
                missing.append(key)

        budget = budget_status(run)
        if budget["exhausted"] and (missing or failed):
            missing.append("budget_exhausted")

        if criteria.evidence_required and not (evidence or {}).get(
            "observations_count", 0
        ):
            missing.append("evidence_insufficient")

        warning_codes = _warning_codes(run.warning_codes, limit_code)
        if failed:
            return CompletionVerdict(
                accepted=False,
                terminal_status=AgentRunStatus.FAILED.value,
                missing_requirements=tuple(sorted(set(failed))),
                warning_codes=warning_codes,
                completion_reason="强制节点失败，无可信结果",
            )

        if missing:
            terminal_status = (
                AgentRunStatus.BLOCKED.value
                if limit_code in _LIMIT_WARNING_CODES
                else AgentRunStatus.PARTIAL.value
            )
            reason = (
                "硬限制已触发，结果缺少必需条件或证据，等待补充后继续"
                if terminal_status == AgentRunStatus.BLOCKED.value
                else "存在未满足的强制条件或证据缺口"
            )
            return CompletionVerdict(
                accepted=False,
                terminal_status=terminal_status,
                missing_requirements=tuple(sorted(set(missing))),
                warning_codes=warning_codes,
                completion_reason=reason,
            )

        if warning_codes:
            return CompletionVerdict(
                accepted=True,
                terminal_status=AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
                warning_codes=warning_codes,
                completion_reason=(
                    "目标满足，但硬限制或其他可解释警告阻止了进一步迭代"
                    if limit_code in _LIMIT_WARNING_CODES
                    else "目标满足但存在已知警告"
                ),
            )

        return CompletionVerdict(
            accepted=True,
            terminal_status=AgentRunStatus.COMPLETED.value,
            completion_reason="所有强制条件与用户目标均已满足",
        )


def _warning_codes(existing, limit_code: str | None) -> tuple[str, ...]:
    values = list(existing or [])
    if limit_code:
        values.append(limit_code)
    return tuple(dict.fromkeys(str(value) for value in values if value))


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
