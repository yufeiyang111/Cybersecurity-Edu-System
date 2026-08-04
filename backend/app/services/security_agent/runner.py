"""Inline plan runner: walks the rule-based policy plan DAG and drives tools.

This is the A1 worker loop.  It executes plans with planner_source =
rule_based_policy inside a background thread (or synchronously when
AGENT_RUN_EXECUTOR=synchronous, used by tests).  RQ workers replace this
dispatcher in batch A10.
"""
from __future__ import annotations

import time
from datetime import datetime

from flask import current_app

from app import db
from app.models.agent_runtime import (
    AgentArtifact,
    AgentPlan,
    AgentPlanEdge,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
    AgentStepExecution,
)
from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.checkpoint_service import CheckpointService
from app.services.security_agent.contracts import (
    EVENT_PLAN_CREATED,
    EVENT_RUN_COMPLETED,
    EVENT_STEP_COMPLETED,
    EVENT_STEP_FAILED,
    EVENT_STEP_STARTED,
    EVENT_WARNING_RAISED,
    PLANNER_RULE_BASED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.state_machine import (
    AgentStateError,
    AgentStateMachine,
)
from app.services.security_agent.tools.contracts import ToolResult
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import get_tool_registry


class InlinePlanRunner:
    """Executes plan nodes for one run with pause/cancel/checkpoint support."""

    def __init__(
        self,
        *,
        state: AgentStateMachine,
        events: EventService,
        artifacts: ArtifactService,
        checkpoints: CheckpointService,
    ) -> None:
        self._state = state
        self._events = events
        self._artifacts = artifacts
        self._checkpoints = checkpoints
        self._tools = ToolExecutor(get_tool_registry(), events)

    def run(self, run_id: int, trace_id: str, app) -> None:
        with app.app_context():
            try:
                run = db.session.get(AgentRun, run_id)
                if run is None:
                    return
                status = self._status_value(run.status)
                plan = self._latest_plan(run.id)

                if status == AgentRunStatus.QUEUED.value:
                    try:
                        self._state.transition(
                            run,
                            AgentRunStatus.PREPARING,
                            actor_id=run.created_by,
                            reason="工作进程开始执行",
                            trace_id=trace_id,
                        )
                    except AgentStateError:
                        run = db.session.get(AgentRun, run_id)
                        if run is not None and self._is_canceled(run):
                            self._cancel_remaining_nodes(run)
                            db.session.commit()
                        return
                    plan = self._build_plan(run, trace_id)
                    self._state.transition(
                        run,
                        AgentRunStatus.EXECUTING_TOOLS,
                        actor_id=run.created_by,
                        reason="开始执行计划节点",
                        trace_id=trace_id,
                    )
                elif status == AgentRunStatus.PREPARING.value:
                    if plan is None:
                        plan = self._build_plan(run, trace_id)
                    self._state.transition(
                        run,
                        AgentRunStatus.EXECUTING_TOOLS,
                        actor_id=run.created_by,
                        reason="恢复执行计划节点",
                        trace_id=trace_id,
                    )
                elif status == AgentRunStatus.EXECUTING_TOOLS.value:
                    if plan is None:
                        plan = self._build_plan(run, trace_id)
                else:
                    return

                self._run_plan_nodes(run, plan, trace_id)
                self._finish_run(run_id, trace_id)
            except Exception:
                db.session.rollback()
                run = db.session.get(AgentRun, run_id)
                if run is None:
                    return
                if not self._is_terminal(run):
                    try:
                        self._state.transition(
                            run,
                            AgentRunStatus.FAILED,
                            actor_id=run.created_by,
                            reason="工作进程异常终止",
                            trace_id=trace_id,
                        )
                        run.error_code = "AGENT_WORKER_CRASH"
                    except AgentStateError:
                        db.session.rollback()
                    db.session.commit()

    def _build_plan(self, run: AgentRun, trace_id: str) -> AgentPlan:
        plan = AgentPlan(
            run_id=run.id,
            plan_version=run.plan_version + 1,
            planner_source=PLANNER_RULE_BASED,
            objective=run.goal_text,
            decision_summary="本地策略基线：先清点快照，再生成运行摘要。",
            completion_criteria_json=["inventory 完成", "report 完成"],
        )
        db.session.add(plan)
        db.session.flush()

        inventory_node = AgentPlanNode(
            plan_id=plan.id,
            node_key="inventory",
            node_type=AgentPlanNodeType.INVENTORY.value,
            status=AgentPlanNodeStatus.READY.value,
            title="清点快照文件",
            description="读取快照文件元数据：文件数、字节数、扩展名与语言分布。",
            tool_name="inventory_snapshot",
        )
        report_node = AgentPlanNode(
            plan_id=plan.id,
            node_key="report",
            node_type=AgentPlanNodeType.REPORT_GENERATION.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title="生成运行摘要",
            description="汇总已完成的确定性证据，生成运行摘要 Artifact。",
            tool_name="finalize_agent_report",
            depends_on_json=["inventory"],
        )
        db.session.add_all([inventory_node, report_node])
        db.session.flush()
        db.session.add(
            AgentPlanEdge(
                plan_id=plan.id,
                from_node="inventory",
                to_node="report",
                edge_type=AgentPlanEdgeType.SUCCESS.value,
            )
        )

        run.plan_version = plan.plan_version
        run.planner_source = plan.planner_source
        self._events.emit(
            run,
            EVENT_PLAN_CREATED,
            {
                "plan_id": plan.id,
                "plan_version": plan.plan_version,
                "planner_source": plan.planner_source,
                "nodes": ["inventory", "report"],
            },
            trace_id=trace_id,
        )
        db.session.commit()
        return plan

    def _run_plan_nodes(self, run: AgentRun, plan: AgentPlan, trace_id: str) -> None:
        restored = self._checkpoints.restore(run.id)
        completed_keys = set(restored.get("completed_node_keys", []))

        for node in sorted(plan.nodes, key=lambda item: item.id):
            if node.node_key in completed_keys:
                continue
            current = db.session.get(AgentRun, run.id)
            if current is None:
                return
            status = self._status_value(current.status)
            if status == AgentRunStatus.PAUSED.value:
                return
            if status == AgentRunStatus.CANCELED.value:
                node.status = AgentPlanNodeStatus.CANCELED.value
                db.session.commit()
                continue
            if status != AgentRunStatus.EXECUTING_TOOLS.value:
                return

            attempt_number = self._next_attempt(node.id)
            step = AgentStepExecution(
                plan_node_id=node.id,
                run_id=run.id,
                attempt_number=attempt_number,
                worker_id="inline-worker",
                status="running",
                started_at=datetime.utcnow(),
            )
            node.status = AgentPlanNodeStatus.RUNNING.value
            db.session.add(step)
            db.session.flush()
            self._events.emit(
                current,
                EVENT_STEP_STARTED,
                {
                    "step_execution_id": step.id,
                    "node_key": node.node_key,
                    "node_type": self._enum_value(node.node_type),
                    "attempt_number": attempt_number,
                    "tool_name": node.tool_name,
                },
                trace_id=trace_id,
            )
            db.session.commit()

            result = self._run_node_tool(current, node, step, trace_id)

            node = db.session.get(AgentPlanNode, node.id)
            step = db.session.get(AgentStepExecution, step.id)
            current = db.session.get(AgentRun, run.id)
            if node is None or step is None or current is None:
                return

            if result.status == "succeeded":
                node.status = AgentPlanNodeStatus.SUCCEEDED.value
                step.status = "completed"
                step.finished_at = datetime.utcnow()
                node.output_artifact_refs = [
                    {"artifact_type": ref["artifact_type"], "summary": ref.get("summary", "")}
                    for ref in result.artifact_refs
                ]
                self._materialize_artifacts(current, node, step, result)
                self._events.emit(
                    current,
                    EVENT_STEP_COMPLETED,
                    {
                        "step_execution_id": step.id,
                        "node_key": node.node_key,
                        "summary": result.summary,
                        "artifact_refs": result.artifact_refs,
                    },
                    trace_id=trace_id,
                )
            else:
                node.status = AgentPlanNodeStatus.FAILED.value
                step.status = "failed"
                step.finished_at = datetime.utcnow()
                step.warning_codes = result.warning_codes
                self._events.emit(
                    current,
                    EVENT_STEP_FAILED,
                    {
                        "step_execution_id": step.id,
                        "node_key": node.node_key,
                        "error_code": result.error_code,
                        "summary": result.summary,
                    },
                    trace_id=trace_id,
                )
                if result.warning_codes:
                    self._events.emit(
                        current,
                        EVENT_WARNING_RAISED,
                        {"warning_codes": result.warning_codes, "node_key": node.node_key},
                        trace_id=trace_id,
                    )

            completed_keys.add(node.node_key)
            self._checkpoints.save(
                current,
                completed_node_keys=sorted(completed_keys),
                artifact_refs=node.output_artifact_refs or [],
            )
            db.session.commit()

            interval = float(current_app.config.get("AGENT_MIN_STEP_INTERVAL_SECONDS", 0.8))
            if interval > 0:
                time.sleep(interval)

    def _run_node_tool(
        self, run: AgentRun, node: AgentPlanNode, step: AgentStepExecution, trace_id: str
    ) -> ToolResult:
        if node.tool_name is None:
            return ToolResult(status="succeeded", summary="节点无需调用工具")
        return self._tools.execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id=trace_id,
        )

    def _finish_run(self, run_id: int, trace_id: str) -> None:
        run = db.session.get(AgentRun, run_id)
        if run is None:
            return
        status = self._status_value(run.status)
        if status in {AgentRunStatus.PAUSED.value, AgentRunStatus.CANCELED.value}:
            return

        plan = self._latest_plan(run.id)
        unfinished = [
            node
            for node in plan.nodes
            if node.status
            in {
                AgentPlanNodeStatus.PENDING.value,
                AgentPlanNodeStatus.READY.value,
                AgentPlanNodeStatus.RUNNING.value,
            }
        ]
        if unfinished:
            self._state.transition(
                run,
                AgentRunStatus.PARTIAL,
                actor_id=run.created_by,
                reason="存在未完成节点，返回部分结果",
                trace_id=trace_id,
            )
            self._events.emit(
                run,
                EVENT_WARNING_RAISED,
                {"warning_codes": ["AGENT_PARTIAL_RESULT"]},
                trace_id=trace_id,
            )
        else:
            self._state.transition(
                run,
                AgentRunStatus.COMPLETED,
                actor_id=run.created_by,
                reason="全部计划节点完成",
                trace_id=trace_id,
            )
            self._events.emit(
                run,
                EVENT_RUN_COMPLETED,
                {
                    "plan_version": run.plan_version,
                    "tool_call_count": run.tool_call_count,
                    "warning_codes": run.warning_codes or [],
                },
                trace_id=trace_id,
            )
        db.session.commit()

    def _materialize_artifacts(
        self, run: AgentRun, node: AgentPlanNode, step: AgentStepExecution, result: ToolResult
    ) -> None:
        for ref in result.artifact_refs:
            artifact_type = ref.get("artifact_type", "artifact")
            self._artifacts.create(
                run,
                artifact_type=artifact_type,
                summary=ref.get("summary", ""),
                content={"metrics": result.metrics} if result.metrics else None,
                sensitive_level="internal",
                plan_node_id=node.id,
                step_execution_id=step.id,
            )

    def _cancel_remaining_nodes(self, run: AgentRun) -> None:
        plan = self._latest_plan(run.id)
        if plan is None:
            return
        for node in plan.nodes:
            if node.status in {
                AgentPlanNodeStatus.PENDING.value,
                AgentPlanNodeStatus.READY.value,
                AgentPlanNodeStatus.RUNNING.value,
            }:
                node.status = AgentPlanNodeStatus.CANCELED.value

    def _latest_plan(self, run_id: int) -> AgentPlan | None:
        return (
            AgentPlan.query.filter_by(run_id=run_id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )

    def _next_attempt(self, plan_node_id: int) -> int:
        latest = (
            AgentStepExecution.query.filter_by(plan_node_id=plan_node_id)
            .order_by(AgentStepExecution.attempt_number.desc())
            .first()
        )
        return (latest.attempt_number + 1) if latest is not None else 1

    def _is_canceled(self, run: AgentRun) -> bool:
        return self._status_value(run.status) == AgentRunStatus.CANCELED.value

    def _is_terminal(self, run: AgentRun) -> bool:
        return self._status_value(run.status) in {
            AgentRunStatus.COMPLETED.value,
            AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
            AgentRunStatus.PARTIAL.value,
            AgentRunStatus.FAILED.value,
            AgentRunStatus.CANCELED.value,
        }

    @staticmethod
    def _status_value(value) -> str:
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _enum_value(value) -> str:
        return value.value if hasattr(value, "value") else str(value)
