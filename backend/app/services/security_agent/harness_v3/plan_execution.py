# -*- coding: utf-8 -*-
"""Harness V3 的确定性计划准备和工具节点执行。"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentRun,
    AgentRunStatus,
    AgentStepExecution,
)
from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.planner import PlanPlanner
from app.services.security_agent.planning.scheduler import PlanScheduler
from app.services.security_agent.state_machine import AgentStateMachine
from app.services.security_agent.tools.contracts import ToolResult

from .runtime_helpers import latest_plan, next_step_attempt, plan_node, status_value

_DEFERRED_NODE_KEYS = frozenset({"deep_review", "report"})


class V3PlanExecutionService:
    """复用既有 Planner/Scheduler/ToolExecutor，只执行确定性基线节点。"""

    def __init__(
        self,
        *,
        state: AgentStateMachine,
        planner: PlanPlanner,
        scheduler: PlanScheduler,
        tool_executor,
        artifacts: ArtifactService,
        worker_id_provider: Callable[[], str | None],
    ) -> None:
        self._state = state
        self._planner = planner
        self._scheduler = scheduler
        self._tool_executor = tool_executor
        self._artifacts = artifacts
        self._worker_id_provider = worker_id_provider

    def prepare_plan(self, run: AgentRun, trace_id: str) -> AgentPlan | None:
        """推进 Preparing/Planning/Validating 并创建或读取计划。"""
        status = status_value(run.status)
        if status == AgentRunStatus.QUEUED.value:
            self._state.transition(
                run,
                AgentRunStatus.PREPARING,
                actor_id=run.created_by,
                reason="Harness V3 工作进程开始执行",
                trace_id=trace_id,
            )
            status = AgentRunStatus.PREPARING.value
        if status == AgentRunStatus.PREPARING.value:
            self._state.transition(
                run,
                AgentRunStatus.PLANNING,
                actor_id=run.created_by,
                reason="生成受限执行计划",
                trace_id=trace_id,
            )
            status = AgentRunStatus.PLANNING.value

        plan = latest_plan(run.id)
        if status == AgentRunStatus.PLANNING.value:
            if plan is None:
                plan = self._planner.generate_plan(run, trace_id=trace_id)
            self._transition_if_needed(
                run,
                AgentRunStatus.VALIDATING_PLAN,
                reason="计划已生成，进入执行前校验",
                trace_id=trace_id,
            )
            status = AgentRunStatus.VALIDATING_PLAN.value
        if status == AgentRunStatus.VALIDATING_PLAN.value:
            self._transition_if_needed(
                run,
                AgentRunStatus.EXECUTING_TOOLS,
                reason="计划校验完成，执行确定性基线",
                trace_id=trace_id,
            )
        return plan or latest_plan(run.id)

    def skip_legacy_free_deep_review(self, plan: AgentPlan) -> None:
        """V3 绝不执行旧计划中包含自由 focus 的 Deep Review 节点。"""
        node = plan_node(plan, "deep_review")
        if node is None:
            return
        if status_value(node.status) in {
            AgentPlanNodeStatus.PENDING.value,
            AgentPlanNodeStatus.READY.value,
        }:
            node.status = AgentPlanNodeStatus.SKIPPED.value
            db.session.commit()

    def execute_baseline_nodes(
        self,
        run: AgentRun,
        trace_id: str,
        apply_controls: Callable[[AgentRun, str], str | None],
    ) -> str | None:
        """执行除 report/deep review 外的已就绪确定性节点。"""
        while True:
            interrupted = apply_controls(run, trace_id)
            if interrupted:
                return interrupted
            plan = latest_plan(run.id)
            if plan is None:
                return None
            schedule = self._scheduler.compute(plan)
            for key in schedule.blocked:
                node = plan_node(plan, key)
                if node is not None and node.node_key not in _DEFERRED_NODE_KEYS:
                    node.status = AgentPlanNodeStatus.BLOCKED.value
            db.session.commit()

            ready_nodes = [
                node
                for node in schedule.ready
                if node.node_key not in _DEFERRED_NODE_KEYS
            ]
            if not ready_nodes:
                return None
            for node in ready_nodes:
                self.execute_node(run, node, trace_id)
                run = db.session.get(AgentRun, run.id)
                if run is None:
                    return "not_found"

    def execute_report_node(
        self,
        run: AgentRun,
        plan: AgentPlan,
        trace_id: str,
    ) -> bool:
        """报告节点只在全部依赖已满足时运行。"""
        report = plan_node(plan, "report")
        if report is None:
            return False
        if status_value(report.status) == AgentPlanNodeStatus.SUCCEEDED.value:
            return True
        if status_value(report.status) in {
            AgentPlanNodeStatus.FAILED.value,
            AgentPlanNodeStatus.BLOCKED.value,
            AgentPlanNodeStatus.CANCELED.value,
        }:
            return False
        schedule = self._scheduler.compute(plan)
        if not any(node.id == report.id for node in schedule.ready):
            return False
        return self.execute_node(run, report, trace_id).status == "succeeded"

    def execute_node(
        self,
        run: AgentRun,
        node: AgentPlanNode,
        trace_id: str,
    ) -> ToolResult:
        """创建节点 Step、执行工具并落受限 Artifact 元数据。"""
        step = AgentStepExecution(
            plan_node_id=node.id,
            run_id=run.id,
            attempt_number=next_step_attempt(node.id),
            worker_id=self._worker_id_provider(),
            status="running",
            started_at=datetime.utcnow(),
        )
        db.session.add(step)
        db.session.flush()
        node.status = AgentPlanNodeStatus.RUNNING.value
        db.session.commit()
        result = self._tool_executor.execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id=trace_id,
            input_payload=node.input_json or None,
        )
        node = db.session.get(AgentPlanNode, node.id)
        step = db.session.get(AgentStepExecution, step.id)
        if node is None or step is None:
            raise RuntimeError("工具执行后计划节点或步骤记录缺失")
        node.status = (
            AgentPlanNodeStatus.SUCCEEDED.value
            if result.status == "succeeded"
            else AgentPlanNodeStatus.FAILED.value
        )
        step.status = result.status
        step.finished_at = datetime.utcnow()
        step.warning_codes = list(result.warning_codes or [])
        self._materialize_artifacts(run, node, step, result)
        db.session.commit()
        return result

    def _materialize_artifacts(
        self,
        run: AgentRun,
        node: AgentPlanNode,
        step: AgentStepExecution,
        result: ToolResult,
    ) -> None:
        for ref in result.artifact_refs:
            self._artifacts.create(
                run,
                artifact_type=ref.get("artifact_type", "artifact"),
                summary=ref.get("summary", ""),
                content={"metrics": result.metrics} if result.metrics else None,
                sensitive_level="internal",
                plan_node_id=node.id,
                step_execution_id=step.id,
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
