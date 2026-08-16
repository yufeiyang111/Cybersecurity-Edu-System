# -*- coding: utf-8 -*-
"""Harness V3 Run 的最终状态与受控完成事件。"""
from __future__ import annotations

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis
from app.models.agent_runtime import AgentPlanNodeStatus, AgentRunStatus
from app.services.security_agent.contracts import EVENT_RUN_COMPLETED
from app.services.security_agent.evidence_evaluator import EvidenceEvaluator
from app.services.security_agent.event_service import EventService
from app.services.security_agent.state_machine import AgentStateMachine

from .runtime_helpers import status_value


class V3RunFinalizer:
    """根据节点与假设的持久化事实收口 Run，不重新解释 Provider 输出。"""

    def __init__(
        self,
        *,
        state: AgentStateMachine,
        events: EventService,
        evidence_evaluator: EvidenceEvaluator,
    ) -> None:
        self._state = state
        self._events = events
        self._evidence_evaluator = evidence_evaluator

    def finish(
        self,
        run,
        plan,
        *,
        report_ok: bool,
        trace_id: str,
    ) -> str:
        """将已完成、告警完成与失败节点明确区分。"""
        summary = self._evidence_evaluator.evaluate(run, plan)
        hypotheses = AgentAuditHypothesis.query.filter_by(run_id=run.id).all()
        unresolved = [
            item
            for item in hypotheses
            if status_value(item.status) not in {"confirmed", "rejected"}
        ]
        failed_nodes = [
            node
            for node in plan.nodes
            if status_value(node.status)
            in {
                AgentPlanNodeStatus.FAILED.value,
                AgentPlanNodeStatus.BLOCKED.value,
                AgentPlanNodeStatus.CANCELED.value,
            }
        ]
        has_warnings = bool(unresolved or failed_nodes or not report_ok)
        target = (
            AgentRunStatus.COMPLETED_WITH_WARNINGS
            if has_warnings
            else AgentRunStatus.COMPLETED
        )
        self._state.transition(
            run,
            target,
            actor_id=run.created_by,
            reason=(
                "Harness V3 已完成，部分候选或计划节点仍存在证据缺口"
                if has_warnings
                else "Harness V3 已完成确定性基线和受限证据审查"
            ),
            trace_id=trace_id,
        )
        self._events.emit(
            run,
            EVENT_RUN_COMPLETED,
            {
                "plan_version": plan.plan_version,
                "hypothesis_count": len(hypotheses),
                "unresolved_hypothesis_count": len(unresolved),
                "failed_node_count": len(failed_nodes),
                "report_completed": report_ok,
                "warning_codes": list(summary.warning_codes),
            },
            trace_id=trace_id,
        )
        db.session.commit()
        return target.value
