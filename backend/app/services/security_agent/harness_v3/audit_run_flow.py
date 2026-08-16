# -*- coding: utf-8 -*-
"""Harness V3 审计任务的阶段状态机编排。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.services.security_agent.evidence_evaluator import EvidenceEvaluator
from app.services.security_agent.harness_v3.finalization import V3RunFinalizer
from app.services.security_agent.harness_v3.hypothesis_planner import HypothesisPlanner
from app.services.security_agent.harness_v3.hypothesis_reviewer import V3HypothesisReviewer
from app.services.security_agent.harness_v3.hypothesis_service import (
    HypothesisPersistenceService,
)
from app.services.security_agent.harness_v3.plan_execution import V3PlanExecutionService
from app.services.security_agent.harness_v3.runtime_helpers import (
    latest_plan,
    run_budget_exhausted,
    status_value,
)
from app.services.security_agent.state_machine import AgentStateMachine


class V3AuditRunFlow:
    """只编排 V3 运行阶段，不承担租约、工具细节或控制输入的实现。"""

    def __init__(
        self,
        *,
        state: AgentStateMachine,
        plan_execution: V3PlanExecutionService,
        evidence_evaluator: EvidenceEvaluator,
        hypothesis_planner: HypothesisPlanner,
        hypothesis_service: HypothesisPersistenceService,
        hypothesis_reviewer: V3HypothesisReviewer,
        control_flow,
        finalizer: V3RunFinalizer,
    ) -> None:
        self._state = state
        self._plan_execution = plan_execution
        self._evidence_evaluator = evidence_evaluator
        self._hypothesis_planner = hypothesis_planner
        self._hypothesis_service = hypothesis_service
        self._hypothesis_reviewer = hypothesis_reviewer
        self._control_flow = control_flow
        self._finalizer = finalizer

    def run(self, run_id: int, trace_id: str) -> str:
        """按“基线 → 假设 → Critic → 报告”的固定 V3 阶段推进。"""
        run = db.session.get(AgentRun, run_id)
        if run is None:
            return "not_found"
        if interrupted := self._control_flow.apply(run, trace_id):
            return interrupted

        plan = self._plan_execution.prepare_plan(run, trace_id)
        if plan is None:
            return status_value(run.status)
        if interrupted := self._control_flow.apply(run, trace_id):
            return interrupted

        if status_value(run.status) == AgentRunStatus.EXECUTING_TOOLS.value:
            self._plan_execution.skip_legacy_free_deep_review(plan)
            if interrupted := self._plan_execution.execute_baseline_nodes(
                run,
                trace_id,
                self._control_flow.apply,
            ):
                return interrupted
            run = db.session.get(AgentRun, run_id)
            if run is None:
                return "not_found"
            self._transition_if_needed(
                run,
                AgentRunStatus.EVALUATING_EVIDENCE,
                reason="确定性基线节点执行完毕，开始评估证据",
                trace_id=trace_id,
            )

        run = db.session.get(AgentRun, run_id)
        plan = latest_plan(run_id)
        if run is None or plan is None:
            return "not_found"
        if interrupted := self._control_flow.apply(run, trace_id):
            return interrupted
        if status_value(run.status) == AgentRunStatus.EVALUATING_EVIDENCE.value:
            self._transition_if_needed(
                run,
                AgentRunStatus.DEEP_REVIEWING,
                reason="基于确定性扫描证据生成受限漏洞假设",
                trace_id=trace_id,
            )

        run = db.session.get(AgentRun, run_id)
        if run is None:
            return "not_found"
        if status_value(run.status) == AgentRunStatus.DEEP_REVIEWING.value:
            evidence_summary = self._evidence_evaluator.evaluate(run, plan)
            batch = self._hypothesis_planner.build(
                run,
                evidence_summary=evidence_summary,
            )
            hypotheses = self._hypothesis_service.persist(run, batch)
            if interrupted := self._hypothesis_reviewer.review(
                run,
                hypotheses,
                trace_id=trace_id,
                apply_controls=self._control_flow.apply,
                budget_exhausted=run_budget_exhausted,
            ):
                return interrupted
            run = db.session.get(AgentRun, run_id)
            if run is None:
                return "not_found"
            self._transition_if_needed(
                run,
                AgentRunStatus.EVALUATING_EVIDENCE,
                reason="漏洞假设已完成受限证据审查",
                trace_id=trace_id,
            )

        run = db.session.get(AgentRun, run_id)
        plan = latest_plan(run_id)
        if run is None or plan is None:
            return "not_found"
        if interrupted := self._control_flow.apply(run, trace_id):
            return interrupted
        if status_value(run.status) == AgentRunStatus.EVALUATING_EVIDENCE.value:
            self._transition_if_needed(
                run,
                AgentRunStatus.GENERATING_REPORT,
                reason="汇总确定性基线和受限漏洞假设",
                trace_id=trace_id,
            )

        run = db.session.get(AgentRun, run_id)
        if run is None:
            return "not_found"
        report_ok = self._plan_execution.execute_report_node(run, plan, trace_id)
        return self._finalizer.finish(
            run,
            plan,
            report_ok=report_ok,
            trace_id=trace_id,
        )

    def _transition_if_needed(
        self,
        run: AgentRun,
        target: AgentRunStatus,
        *,
        reason: str,
        trace_id: str,
    ) -> None:
        if status_value(run.status) == target.value:
            return
        self._state.transition(
            run,
            target,
            actor_id=run.created_by,
            reason=reason,
            trace_id=trace_id,
        )
