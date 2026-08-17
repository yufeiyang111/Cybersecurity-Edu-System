# -*- coding: utf-8 -*-
"""Harness V3 假设执行后的独立证据判定编排。"""
from __future__ import annotations

from collections.abc import Callable

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis
from app.models.agent_review import AgentObservation
from app.services.security_agent.harness_v3.evidence_critic import (
    EvidenceCritic,
    HypothesisEvidence,
    HypothesisEvidenceLocation,
)
from app.services.security_agent.harness_v3.execution import (
    HypothesisExecutionOrchestrator,
)
from app.services.security_agent.harness_v3.hypothesis_service import (
    HypothesisPersistenceService,
)
from app.services.security_agent.harness_v3.reasoning_summary import (
    V3ReasoningSummaryService,
)


class V3HypothesisReviewer:
    """每个假设最多主审一次、Critic 请求时补证据一次。"""

    def __init__(
        self,
        *,
        hypothesis_service: HypothesisPersistenceService,
        critic: EvidenceCritic,
        reasoning_summaries: V3ReasoningSummaryService,
        tool_executor,
    ) -> None:
        self._hypothesis_service = hypothesis_service
        self._critic = critic
        self._reasoning_summaries = reasoning_summaries
        self._tool_executor = tool_executor

    def review(
        self,
        run,
        hypotheses: tuple[AgentAuditHypothesis, ...],
        *,
        trace_id: str,
        apply_controls: Callable[[object, str], str | None],
        budget_exhausted: Callable[[object], bool],
    ) -> str | None:
        """按有界 ReAct → Critic → 最多一次补审推进所有假设。"""
        if not hypotheses:
            return None
        executor = HypothesisExecutionOrchestrator(
            tool_executor=self._tool_executor,
        )
        for hypothesis in hypotheses:
            interrupted = apply_controls(run, trace_id)
            if interrupted:
                return interrupted
            review_kind = (
                "primary"
                if int(hypothesis.execution_attempt_count or 0) == 0
                else "supplemental"
            )
            self._reasoning_summaries.emit_action(
                run,
                hypothesis,
                review_kind=review_kind,
                trace_id=trace_id,
            )
            outcome = executor.advance(run, hypothesis, trace_id=trace_id)
            decision = self._critic.evaluate(
                hypothesis,
                self._evidence_for(outcome.observation_id, outcome.reason_code),
                budget_exhausted=budget_exhausted(run),
            )
            self._hypothesis_service.record_verdict(hypothesis, decision)
            self._reasoning_summaries.emit_decision(
                run,
                hypothesis,
                decision,
                review_kind=outcome.review_kind,
                trace_id=trace_id,
            )
            if decision.next_action.get("action") != "request_supplemental_review":
                continue

            refreshed = db.session.get(AgentAuditHypothesis, hypothesis.id)
            if refreshed is None:
                continue
            interrupted = apply_controls(run, trace_id)
            if interrupted:
                return interrupted
            self._reasoning_summaries.emit_action(
                run,
                refreshed,
                review_kind="supplemental",
                trace_id=trace_id,
            )
            supplemental = executor.advance(run, refreshed, trace_id=trace_id)
            decision = self._critic.evaluate(
                refreshed,
                self._evidence_for(
                    supplemental.observation_id,
                    supplemental.reason_code,
                ),
                budget_exhausted=budget_exhausted(run),
            )
            self._hypothesis_service.record_verdict(refreshed, decision)
            self._reasoning_summaries.emit_decision(
                run,
                refreshed,
                decision,
                review_kind=supplemental.review_kind,
                trace_id=trace_id,
            )
        return None

    @staticmethod
    def _evidence_for(
        observation_id: int | None,
        reason_code: str | None,
    ) -> HypothesisEvidence:
        if observation_id is None:
            return HypothesisEvidence(
                observation_id=None,
                locations=(),
                claimed_satisfied=(),
                proof_gaps=(reason_code or "未产生可核验 Observation",),
            )
        observation = db.session.get(AgentObservation, observation_id)
        if observation is None:
            return HypothesisEvidence(
                observation_id=observation_id,
                locations=(),
                claimed_satisfied=(),
                proof_gaps=("Observation 不可读取",),
            )
        locations = tuple(
            HypothesisEvidenceLocation(
                file_path=location.file_path,
                start_line=location.start_line,
                end_line=location.end_line or location.start_line,
                role=location.role,
            )
            for location in observation.locations
        )
        detail = observation.detail_json if isinstance(observation.detail_json, dict) else {}
        claims = detail.get("v3_evidence_satisfied", [])
        controls = detail.get("v3_control_assessments", {})
        control_assessments = tuple(
            (key, value)
            for key, value in controls.items()
            if isinstance(key, str) and key and isinstance(value, str) and value
        ) if isinstance(controls, dict) else ()
        return HypothesisEvidence(
            observation_id=observation.id,
            locations=locations,
            claimed_satisfied=tuple(
                value
                for value in claims
                if isinstance(value, str) and value
            ),
            proof_gaps=tuple(
                str(value)
                for value in (observation.proof_gaps_json or [])
                if str(value)
            ),
            control_assessments=control_assessments,
        )
