# -*- coding: utf-8 -*-
"""Harness V3 的暂停、取消和有序控制输入处理。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import AgentPlanNodeStatus, AgentRun, AgentRunStatus
from app.services.security_agent.loop.control_inputs import ControlInputService
from app.services.security_agent.state_machine import AgentStateMachine

from .runtime_helpers import latest_plan, status_value


class V3RunControlService:
    """所有控制输入先持久化再由 Worker 应用，Route 绝不直接执行工具。"""

    def __init__(
        self,
        *,
        state: AgentStateMachine,
        controls: ControlInputService,
    ) -> None:
        self._state = state
        self._controls = controls

    def apply(self, run, trace_id: str) -> str | None:
        """返回 interrupt/canceled/not_found，空值表示本轮可继续。"""
        refreshed = db.session.get(AgentRun, run.id)
        if refreshed is None:
            return "not_found"
        status = status_value(refreshed.status)
        if status == AgentRunStatus.CANCEL_REQUESTED.value:
            return self._complete_cancel(refreshed, trace_id)
        if status == AgentRunStatus.PAUSED.value:
            return "interrupted"

        for control in self._controls.list_pending(refreshed.id):
            self._controls.apply(
                control,
                iteration=int(refreshed.iteration_count or 0),
                trace_id=trace_id,
            )
            if control.input_type == "cancel":
                self._transition_if_needed(
                    refreshed,
                    AgentRunStatus.CANCEL_REQUESTED,
                    reason="控制输入：取消请求已接收",
                    trace_id=trace_id,
                )
                return self._complete_cancel(refreshed, trace_id)
            if control.input_type == "pause":
                if self._state.can_transition(
                    status_value(refreshed.status),
                    AgentRunStatus.PAUSED.value,
                ):
                    self._state.transition(
                        refreshed,
                        AgentRunStatus.PAUSED,
                        actor_id=refreshed.created_by,
                        reason="控制输入：暂停",
                        trace_id=trace_id,
                    )
                return "interrupted"
        return None

    def _complete_cancel(self, run, trace_id: str) -> str:
        plan = latest_plan(run.id)
        if plan is not None:
            for node in plan.nodes:
                if status_value(node.status) in {
                    AgentPlanNodeStatus.PENDING.value,
                    AgentPlanNodeStatus.READY.value,
                    AgentPlanNodeStatus.RUNNING.value,
                }:
                    node.status = AgentPlanNodeStatus.CANCELED.value
        self._state.transition(
            run,
            AgentRunStatus.CANCELED,
            actor_id=run.created_by,
            reason="未执行节点已取消，Harness V3 安全结束",
            trace_id=trace_id,
        )
        db.session.commit()
        return AgentRunStatus.CANCELED.value

    def _transition_if_needed(
        self,
        run,
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
