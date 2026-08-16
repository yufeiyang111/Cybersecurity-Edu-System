# -*- coding: utf-8 -*-
"""Harness V3 假设与 Critic 判定的无源码持久化服务。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.agent_hypothesis import (
    AgentAuditHypothesis,
    AgentAuditHypothesisVerdict,
    AuditHypothesisStatus,
    AuditHypothesisVerdict,
)
from app.models.agent_runtime import AgentRun
from app.services.security_agent.hypotheses.validator import HypothesisValidator

if TYPE_CHECKING:
    from app.services.security_agent.harness_v3.evidence_critic import CriticDecision
    from app.services.security_agent.harness_v3.hypothesis_planner import (
        HypothesisPlanBatch,
    )


class HypothesisPersistenceService:
    """持久化严格校验过的结构化假设和 Critic 决策。"""

    def __init__(self) -> None:
        self._validator = HypothesisValidator()

    def persist(
        self,
        run: AgentRun,
        batch: "HypothesisPlanBatch",
    ) -> tuple[AgentAuditHypothesis, ...]:
        """幂等创建 Run 内假设；不覆盖已执行假设，也不保存源码或 Provider 原文。"""
        existing = {
            item.hypothesis_key: item
            for item in AgentAuditHypothesis.query.filter_by(run_id=run.id).all()
        }
        persisted: list[AgentAuditHypothesis] = []
        for draft in batch.drafts:
            self._validator.validate_batch(
                (draft,),
                allowed_scopes=draft.authorized_scopes,
            )
            item = existing.get(draft.hypothesis_key)
            if item is None:
                item = AgentAuditHypothesis(
                    run_id=run.id,
                    hypothesis_key=draft.hypothesis_key,
                    skill_key=draft.skill_key,
                    title=draft.title,
                    target_summary=draft.target_summary,
                    priority=draft.priority,
                    status=AuditHypothesisStatus.QUEUED.value,
                    planner_source=draft.planner_source,
                    required_evidence_json=list(draft.required_evidence),
                    authorized_scopes_json=[
                        scope.to_dict()
                        for scope in draft.authorized_scopes
                    ],
                    satisfied_evidence_json=[],
                    evidence_gaps_json=list(draft.required_evidence),
                )
                db.session.add(item)
                existing[draft.hypothesis_key] = item
            persisted.append(item)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            persisted = [
                AgentAuditHypothesis.query.filter_by(
                    run_id=run.id,
                    hypothesis_key=draft.hypothesis_key,
                ).one()
                for draft in batch.drafts
            ]
        return tuple(
            sorted(
                persisted,
                key=lambda item: (-item.priority, item.id or 0),
            )
        )

    def record_verdict(
        self,
        hypothesis: AgentAuditHypothesis,
        decision: "CriticDecision",
    ) -> AgentAuditHypothesisVerdict:
        """追加版本化判定，同时同步假设的受控状态摘要。"""
        verdict_value = AuditHypothesisVerdict(decision.verdict)
        latest = (
            AgentAuditHypothesisVerdict.query.filter_by(
                hypothesis_id=hypothesis.id
            )
            .order_by(AgentAuditHypothesisVerdict.verdict_version.desc())
            .first()
        )
        record = AgentAuditHypothesisVerdict(
            hypothesis_id=hypothesis.id,
            verdict_version=(
                latest.verdict_version
                if latest is not None
                else 0
            )
            + 1,
            verdict=verdict_value.value,
            reason_summary=str(decision.reason_summary)[:2000],
            evidence_gaps_json=list(decision.evidence_gaps),
            next_action_json=dict(decision.next_action),
            critic_version=str(decision.critic_version)[:64],
        )
        hypothesis.satisfied_evidence_json = list(decision.satisfied_evidence)
        hypothesis.evidence_gaps_json = list(decision.evidence_gaps)
        hypothesis.status = _status_for_verdict(verdict_value)
        db.session.add(record)
        db.session.commit()
        return record


def _status_for_verdict(verdict: AuditHypothesisVerdict) -> str:
    if verdict == AuditHypothesisVerdict.CONFIRM_CANDIDATE:
        return AuditHypothesisStatus.CONFIRMED.value
    if verdict == AuditHypothesisVerdict.REJECT_HYPOTHESIS:
        return AuditHypothesisStatus.REJECTED.value
    if verdict == AuditHypothesisVerdict.STOP_FOR_BUDGET:
        return AuditHypothesisStatus.STOPPED_FOR_BUDGET.value
    return AuditHypothesisStatus.NEEDS_EVIDENCE.value
