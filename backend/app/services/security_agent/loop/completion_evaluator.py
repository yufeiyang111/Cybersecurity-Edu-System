# -*- coding: utf-8 -*-
"""CompletionEvaluator（T08，spec §11）：完成判定与五种终态。

判定依据：模式强制节点、覆盖、证据、失败、警告、预算与用户目标；
任何终态都必须由本 Evaluator 产生，Runner 不得自行"跑完即成功"。
"""
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

# 强制节点中失败/缺失的语义
_FAILED_STATUSES = frozenset({AgentPlanNodeStatus.FAILED.value})
_MISSING_STATUSES = frozenset(
    {
        AgentPlanNodeStatus.PENDING.value,
        AgentPlanNodeStatus.READY.value,
        AgentPlanNodeStatus.RUNNING.value,
        AgentPlanNodeStatus.BLOCKED.value,
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
    ) -> CompletionVerdict:
        """按模式与证据判定终态；plan 为 None 时按无可信结果处理。"""
        status = _status_value(run.status)
        if status == AgentRunStatus.CANCELED.value:
            return CompletionVerdict(
                accepted=False,
                terminal_status="canceled",
                missing_requirements=(),
                warning_codes=(),
                completion_reason="用户取消",
            )

        criteria = CompletionCriteria.for_mode(_status_value(run.mode))
        missing: list[str] = []
        failed: list[str] = []
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

        warning_codes = tuple(run.warning_codes or [])
        if failed:
            return CompletionVerdict(
                accepted=False,
                terminal_status="failed",
                missing_requirements=tuple(sorted(set(failed))),
                warning_codes=warning_codes,
                completion_reason="强制节点失败，无可信结果",
            )
        if missing:
            return CompletionVerdict(
                accepted=False,
                terminal_status="partial",
                missing_requirements=tuple(sorted(set(missing))),
                warning_codes=warning_codes,
                completion_reason="存在未满足的强制条件或证据缺口",
            )
        if warning_codes:
            return CompletionVerdict(
                accepted=True,
                terminal_status="completed_with_warnings",
                missing_requirements=(),
                warning_codes=warning_codes,
                completion_reason="目标满足但存在已知警告",
            )
        return CompletionVerdict(
            accepted=True,
            terminal_status="completed",
            missing_requirements=(),
            warning_codes=(),
            completion_reason="所有强制条件与用户目标均已满足",
        )


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
