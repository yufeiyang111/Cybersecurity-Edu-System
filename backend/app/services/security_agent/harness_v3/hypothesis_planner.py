# -*- coding: utf-8 -*-
"""Harness V3 的受限漏洞假设规划协调器。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

from app.models.agent_runtime import AgentRun
from app.services.llm.provider_selector import select_provider
from app.services.security_agent.audit_skills import AuditSkill, AuditSkillCatalog
from app.services.security_agent.budget import budget_status
from app.services.security_agent.harness_v3.budget import deep_review_token_reserve
from app.services.security_agent.hypotheses.contracts import AuditHypothesisDraft
from app.services.security_agent.hypotheses.validator import (
    HypothesisValidationError,
    HypothesisValidator,
)

from .planner_provider import (
    HYPOTHESIS_PLANNER_OPERATION,
    ProviderHypothesisDraftBuilder,
)
from .planner_signals import (
    MAX_FINDING_SIGNALS,
    FindingSignal,
    max_hypotheses,
    make_hypothesis_draft,
    read_finding_signals,
    run_mode,
    scopes_for_skill,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HypothesisPlanBatch:
    """规划器的受限输出；所有 Draft 仍须经过持久化服务校验。"""

    drafts: tuple[AuditHypothesisDraft, ...]
    planner_source: str
    fallback_reason: str | None
    finding_signals: tuple[FindingSignal, ...]


class HypothesisPlanner:
    """在 Provider 与规则降级之间协调最多三条受控攻击路径假设。"""

    def __init__(
        self,
        *,
        catalog: AuditSkillCatalog | None = None,
        provider_selector: Callable[..., object | None] | None = None,
        finding_reader: Callable[[AgentRun], Iterable[FindingSignal]] | None = None,
        provider_draft_builder: ProviderHypothesisDraftBuilder | None = None,
    ) -> None:
        self._catalog = catalog or AuditSkillCatalog()
        self._validator = HypothesisValidator(self._catalog)
        self._provider_selector = provider_selector or select_provider
        self._finding_reader = finding_reader or read_finding_signals
        self._provider_draft_builder = (
            provider_draft_builder
            or ProviderHypothesisDraftBuilder(
                catalog=self._catalog,
                validator=self._validator,
            )
        )

    def build(
        self,
        run: AgentRun,
        *,
        evidence_summary: object | None,
    ) -> HypothesisPlanBatch:
        """规划候选，并在 Provider 失败或违规输出时显式回退规则策略。"""
        signals = tuple(self._finding_reader(run))[:MAX_FINDING_SIGNALS]
        skills = self._catalog.select(
            snapshot_summary=None,
            evidence_summary=evidence_summary,
            run_mode=run_mode(run),
            finding_signals=signals,
            limit=max_hypotheses(),
        )
        if not skills:
            return HypothesisPlanBatch(
                drafts=(),
                planner_source="rule_based_policy",
                fallback_reason="no_matching_finding_signals",
                finding_signals=signals,
            )

        provider = self._provider_selector(
            user_id=run.created_by,
            operation=HYPOTHESIS_PLANNER_OPERATION,
        )
        if provider is None:
            return self._rule_batch(
                run,
                skills,
                signals,
                fallback_reason="provider_unavailable",
            )
        if not self._budget_allows_planner(run):
            return self._rule_batch(
                run,
                skills,
                signals,
                fallback_reason="budget_reserved_for_deep_review",
            )

        try:
            drafts = self._provider_draft_builder.build(
                run,
                provider=provider,
                skills=skills,
                signals=signals,
            )
        except (HypothesisValidationError, ValueError, TypeError) as exc:
            logger.warning(
                "Harness V3 hypothesis planner rejected provider output "
                "(run_id=%s, error_type=%s)",
                run.id,
                type(exc).__name__,
            )
            return self._rule_batch(
                run,
                skills,
                signals,
                fallback_reason="provider_output_invalid",
            )
        except (OSError, RuntimeError, TimeoutError) as exc:
            logger.warning(
                "Harness V3 hypothesis planner provider failed "
                "(run_id=%s, error_type=%s)",
                run.id,
                type(exc).__name__,
            )
            return self._rule_batch(
                run,
                skills,
                signals,
                fallback_reason="provider_request_failed",
            )

        if not drafts:
            return self._rule_batch(
                run,
                skills,
                signals,
                fallback_reason="provider_output_invalid",
            )
        return HypothesisPlanBatch(
            drafts=drafts,
            planner_source="llm_live",
            fallback_reason=None,
            finding_signals=signals,
        )

    def _rule_batch(
        self,
        run: AgentRun,
        skills: tuple[AuditSkill, ...],
        signals: tuple[FindingSignal, ...],
        *,
        fallback_reason: str,
    ) -> HypothesisPlanBatch:
        drafts: list[AuditHypothesisDraft] = []
        for skill in skills:
            scopes = scopes_for_skill(skill, signals)
            if not scopes:
                continue
            draft = make_hypothesis_draft(
                run=run,
                skill=skill,
                scopes=scopes,
                priority=80,
                planner_source="rule_based_policy",
            )
            self._validator.validate_batch(
                (draft,),
                allowed_scopes=scopes,
            )
            drafts.append(draft)
        return HypothesisPlanBatch(
            drafts=tuple(drafts),
            planner_source="rule_based_policy",
            fallback_reason=fallback_reason,
            finding_signals=signals,
        )

    @staticmethod
    def _budget_allows_planner(run: AgentRun) -> bool:
        status = budget_status(run)
        if status["exhausted"]:
            return False
        maximum = run.max_total_tokens
        if maximum is None or maximum <= 0:
            return True
        return maximum - int(run.total_tokens or 0) > deep_review_token_reserve()


__all__ = [
    "FindingSignal",
    "HypothesisPlanBatch",
    "HypothesisPlanner",
]
