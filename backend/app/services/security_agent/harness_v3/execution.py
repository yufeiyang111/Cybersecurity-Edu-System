# -*- coding: utf-8 -*-
"""Harness V3 假设绑定的受限 ReAct 执行器。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis, AuditHypothesisStatus
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentStepExecution,
    AgentToolCall,
)
from app.services.security_agent.audit_skills import AuditSkillCatalog
from app.services.security_agent.tools.contracts import ToolResult


@dataclass(frozen=True)
class HypothesisExecutionResult:
    """一次假设绑定 Deep Review 的可审计结果摘要。"""

    hypothesis_id: int
    review_kind: str
    made_progress: bool
    reason_code: str | None
    observation_id: int | None
    plan_node_id: int | None
    step_execution_id: int | None
    tool_result: ToolResult | None


class HypothesisExecutionOrchestrator:
    """每条假设最多主审一次、补充审一次；工具输入没有自由 focus 或路径。"""

    def __init__(
        self,
        *,
        tool_executor,
        catalog: AuditSkillCatalog | None = None,
    ) -> None:
        self._tool_executor = tool_executor
        self._catalog = catalog or AuditSkillCatalog()

    def advance(
        self,
        run: AgentRun,
        hypothesis: AgentAuditHypothesis,
        *,
        trace_id: str | None,
    ) -> HypothesisExecutionResult:
        """推进一轮受限审查；计数只在此处增加，避免 Tool Handler 双重记账。"""
        if hypothesis.run_id != run.id:
            raise ValueError("漏洞假设不属于当前任务")
        skill = self._catalog.require(hypothesis.skill_key)
        attempt_count = int(hypothesis.execution_attempt_count or 0)
        if attempt_count >= skill.max_attempts:
            hypothesis.status = AuditHypothesisStatus.NEEDS_EVIDENCE.value
            db.session.commit()
            return HypothesisExecutionResult(
                hypothesis_id=hypothesis.id,
                review_kind="supplemental" if attempt_count else "primary",
                made_progress=False,
                reason_code="AGENT_V3_HYPOTHESIS_ATTEMPT_LIMIT",
                observation_id=None,
                plan_node_id=None,
                step_execution_id=None,
                tool_result=None,
            )

        review_kind = "primary" if attempt_count == 0 else "supplemental"
        plan = self._latest_plan(run.id)
        if plan is None:
            raise ValueError("漏洞假设执行前必须已有持久化计划")
        node = self._node_for(plan, hypothesis, review_kind)
        step = self._new_step(run, node)
        payload = {
            "hypothesis_id": hypothesis.id,
            "skill_key": hypothesis.skill_key,
            "required_evidence": list(hypothesis.required_evidence_json or []),
            "review_kind": review_kind,
        }

        node.status = AgentPlanNodeStatus.RUNNING.value
        hypothesis.status = AuditHypothesisStatus.ACTIVE.value
        db.session.commit()
        result = self._tool_executor.execute(
            run,
            node,
            step,
            actor_id=run.created_by,
            trace_id=trace_id,
            input_payload=payload,
        )
        node = db.session.get(AgentPlanNode, node.id)
        hypothesis = db.session.get(AgentAuditHypothesis, hypothesis.id)
        step = db.session.get(AgentStepExecution, step.id)
        if node is None or hypothesis is None or step is None:
            raise RuntimeError("假设审查执行记录在工具调用后不可用")

        node.status = (
            AgentPlanNodeStatus.SUCCEEDED.value
            if result.status == "succeeded"
            else AgentPlanNodeStatus.FAILED.value
        )
        step.status = result.status
        step.finished_at = datetime.utcnow()
        step.warning_codes = list(result.warning_codes or [])
        hypothesis.execution_attempt_count = attempt_count + 1
        if review_kind == "supplemental":
            hypothesis.reflection_count = int(hypothesis.reflection_count or 0) + 1

        tool_call = (
            AgentToolCall.query.filter_by(step_execution_id=step.id)
            .order_by(AgentToolCall.id.desc())
            .first()
        )
        if tool_call is not None:
            hypothesis.related_tool_call_id = tool_call.id

        observation_id = _positive_int((result.metrics or {}).get("observation_id"))
        made_progress = result.status == "succeeded" and observation_id is not None
        if not made_progress:
            hypothesis.status = AuditHypothesisStatus.NEEDS_EVIDENCE.value
        reason_code = None
        if not made_progress:
            reason_code = result.error_code or _first_warning(result) or "AGENT_V3_DEEP_REVIEW_NO_PROGRESS"
        db.session.commit()
        return HypothesisExecutionResult(
            hypothesis_id=hypothesis.id,
            review_kind=review_kind,
            made_progress=made_progress,
            reason_code=reason_code,
            observation_id=observation_id,
            plan_node_id=node.id,
            step_execution_id=step.id,
            tool_result=result,
        )

    @staticmethod
    def _latest_plan(run_id: int) -> AgentPlan | None:
        return (
            AgentPlan.query.filter_by(run_id=run_id)
            .order_by(AgentPlan.plan_version.desc(), AgentPlan.id.desc())
            .first()
        )

    @staticmethod
    def _node_for(
        plan: AgentPlan,
        hypothesis: AgentAuditHypothesis,
        review_kind: str,
    ) -> AgentPlanNode:
        node_key = f"v3_hypothesis_{hypothesis.id}_{review_kind}"
        node = AgentPlanNode.query.filter_by(plan_id=plan.id, node_key=node_key).first()
        if node is not None:
            return node
        review_label = "主审" if review_kind == "primary" else "补充审查"
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key=node_key,
            node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title=f"{hypothesis.title}：{review_label}",
            description="仅依据已持久化的假设、证据条件和授权代码范围执行 Deep Review。",
            tool_name="run_deep_review",
            input_json={
                "hypothesis_id": hypothesis.id,
                "skill_key": hypothesis.skill_key,
                "required_evidence": list(hypothesis.required_evidence_json or []),
                "review_kind": review_kind,
            },
            depends_on_json=[],
        )
        db.session.add(node)
        db.session.flush()
        return node

    @staticmethod
    def _new_step(run: AgentRun, node: AgentPlanNode) -> AgentStepExecution:
        previous = (
            AgentStepExecution.query.filter_by(plan_node_id=node.id)
            .order_by(AgentStepExecution.attempt_number.desc())
            .first()
        )
        step = AgentStepExecution(
            plan_node_id=node.id,
            run_id=run.id,
            attempt_number=(previous.attempt_number if previous is not None else 0) + 1,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.session.add(step)
        db.session.flush()
        return step


def _positive_int(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return value


def _first_warning(result: ToolResult) -> str | None:
    for warning in result.warning_codes or []:
        if isinstance(warning, str) and warning:
            return warning
    return None
