# -*- coding: utf-8 -*-
"""Harness V3 的顶层协调器：只负责依赖装配、租约和故障收口。"""
from __future__ import annotations

import logging
import os
from uuid import uuid4

from flask import current_app

from app import db
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.evidence_evaluator import EvidenceEvaluator
from app.services.security_agent.event_service import EventService
from app.services.security_agent.feature_flags import AgentFeatureFlags
from app.services.security_agent.harness_v3.audit_run_flow import V3AuditRunFlow
from app.services.security_agent.harness_v3.control_flow import V3RunControlService
from app.services.security_agent.harness_v3.evidence_critic import EvidenceCritic
from app.services.security_agent.harness_v3.finalization import V3RunFinalizer
from app.services.security_agent.harness_v3.hypothesis_planner import HypothesisPlanner
from app.services.security_agent.harness_v3.hypothesis_reviewer import V3HypothesisReviewer
from app.services.security_agent.harness_v3.hypothesis_service import HypothesisPersistenceService
from app.services.security_agent.harness_v3.plan_execution import V3PlanExecutionService
from app.services.security_agent.harness_v3.reasoning_summary import V3ReasoningSummaryService
from app.services.security_agent.harness_v3.runtime_helpers import mode_value, status_value
from app.services.security_agent.loop.control_inputs import ControlInputService
from app.services.security_agent.loop.lease_service import LeaseError, LeaseService
from app.services.security_agent.planner import PlanPlanner
from app.services.security_agent.planning.scheduler import PlanScheduler
from app.services.security_agent.state_machine import AgentStateError, AgentStateMachine
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = frozenset(
    {
        AgentRunStatus.COMPLETED.value,
        AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
        AgentRunStatus.BLOCKED.value,
        AgentRunStatus.PARTIAL.value,
        AgentRunStatus.FAILED.value,
        AgentRunStatus.CANCELED.value,
    }
)


class HarnessV3Coordinator:
    """协调确定性基线、受限 ReAct 和独立 Critic，不承载具体工具细节。"""

    def __init__(
        self,
        *,
        state: AgentStateMachine | None = None,
        events: EventService | None = None,
        planner: PlanPlanner | None = None,
        scheduler: PlanScheduler | None = None,
        evidence_evaluator: EvidenceEvaluator | None = None,
        hypothesis_planner: HypothesisPlanner | None = None,
        hypothesis_service: HypothesisPersistenceService | None = None,
        critic: EvidenceCritic | None = None,
        reasoning_summaries: V3ReasoningSummaryService | None = None,
        tool_executor=None,
        artifacts: ArtifactService | None = None,
        leases: LeaseService | None = None,
        controls: ControlInputService | None = None,
    ) -> None:
        self._state = state or AgentStateMachine()
        self._events = events or EventService()
        self._planner = planner or PlanPlanner(self._events)
        self._scheduler = scheduler or PlanScheduler()
        self._evidence_evaluator = evidence_evaluator or EvidenceEvaluator()
        self._hypothesis_planner = hypothesis_planner or HypothesisPlanner()
        self._hypothesis_service = hypothesis_service or HypothesisPersistenceService()
        self._critic = critic or EvidenceCritic()
        self._reasoning_summaries = reasoning_summaries or V3ReasoningSummaryService()
        self._artifacts = artifacts or ArtifactService()
        self._leases = leases or LeaseService()
        self._controls = controls or ControlInputService()
        self._lease_owner: str | None = None
        self._tool_executor = tool_executor or ToolExecutor(
            get_tool_registry(),
            self._events,
            heartbeat=self._heartbeat,
        )
        control_flow = V3RunControlService(
            state=self._state,
            controls=self._controls,
        )
        plan_execution = V3PlanExecutionService(
            state=self._state,
            planner=self._planner,
            scheduler=self._scheduler,
            tool_executor=self._tool_executor,
            artifacts=self._artifacts,
            worker_id_provider=lambda: self._lease_owner,
        )
        hypothesis_reviewer = V3HypothesisReviewer(
            hypothesis_service=self._hypothesis_service,
            critic=self._critic,
            reasoning_summaries=self._reasoning_summaries,
            tool_executor=self._tool_executor,
        )
        finalizer = V3RunFinalizer(
            state=self._state,
            events=self._events,
            evidence_evaluator=self._evidence_evaluator,
        )
        self._flow = V3AuditRunFlow(
            state=self._state,
            plan_execution=plan_execution,
            evidence_evaluator=self._evidence_evaluator,
            hypothesis_planner=self._hypothesis_planner,
            hypothesis_service=self._hypothesis_service,
            hypothesis_reviewer=hypothesis_reviewer,
            control_flow=control_flow,
            finalizer=finalizer,
        )

    def run_hybrid_or_deep(self, run_id: int, trace_id: str) -> str:
        """运行一个灰度 V3 Hybrid/Deep Audit，状态与租约始终受统一约束。"""
        run = db.session.get(AgentRun, run_id)
        if run is None:
            return "not_found"
        if not self._is_v3_run(run):
            return "not_applicable"
        if status_value(run.status) in _TERMINAL_STATUSES:
            return status_value(run.status)

        owner = self._owner()
        if not self._leases.acquire(run.id, owner, lease_seconds=self._lease_seconds()):
            return "lease_not_acquired"
        self._lease_owner = owner
        try:
            return self._flow.run(run.id, trace_id)
        except Exception as exc:  # noqa: BLE001 - 顶层必须安全收口未知工作进程异常。
            logger.exception(
                "Harness V3 coordinator crashed (run_id=%s, error_type=%s)",
                run_id,
                type(exc).__name__,
            )
            db.session.rollback()
            self._mark_crashed_run(run_id, trace_id)
            return AgentRunStatus.FAILED.value
        finally:
            self._release_lease(run_id, owner)
            self._lease_owner = None

    def _mark_crashed_run(self, run_id: int, trace_id: str) -> None:
        run = db.session.get(AgentRun, run_id)
        if run is None or status_value(run.status) in _TERMINAL_STATUSES:
            return
        try:
            self._state.transition(
                run,
                AgentRunStatus.FAILED,
                actor_id=run.created_by,
                reason="Harness V3 协调器异常终止",
                trace_id=trace_id,
            )
            run.error_code = "AGENT_HARNESS_V3_CRASH"
            db.session.commit()
        except AgentStateError:
            db.session.rollback()

    @staticmethod
    def _is_v3_run(run: AgentRun) -> bool:
        flags = AgentFeatureFlags().for_run(run)
        return bool(flags.harness_v3) and mode_value(run) in {"hybrid", "deep_audit"}

    def _heartbeat(self, run_id: int) -> None:
        if self._lease_owner:
            self._leases.heartbeat(run_id, self._lease_owner)

    @staticmethod
    def _lease_seconds() -> int:
        value = current_app.config.get("AGENT_LOOP_LEASE_SECONDS", 60)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 60

    @staticmethod
    def _owner() -> str:
        configured = current_app.config.get("AGENT_WORKER_ID")
        if configured:
            return f"harness-v3-{configured}-{uuid4().hex[:8]}"
        return f"harness-v3-{os.getpid()}-{uuid4().hex[:8]}"

    def _release_lease(self, run_id: int, owner: str) -> None:
        try:
            self._leases.release(run_id, owner)
        except LeaseError:
            logger.warning(
                "Harness V3 lease already changed before release (run_id=%s)",
                run_id,
            )
