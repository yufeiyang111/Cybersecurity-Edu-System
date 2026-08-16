# -*- coding: utf-8 -*-
"""Agent Run 统一统计：只聚合可审计的持久化计数，不拼接源码或 Prompt。"""
from __future__ import annotations

from app.models.agent_approval import AgentApproval
from app.models.agent_review import AgentObservation, AgentObservationLocation
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNodeStatus,
    AgentRun,
    AgentToolCall,
)

_COMPLETED_NODE_STATUSES = frozenset({"succeeded", "completed"})
_SUCCESSFUL_TOOL_STATUSES = frozenset({"succeeded", "completed"})
_FAILED_TOOL_STATUSES = frozenset({"failed", "timeout", "canceled", "cancelled"})


def build_run_statistics(run: AgentRun, plan: AgentPlan | None) -> dict[str, int]:
    """返回 Run 详情使用的统一统计字段。

    统计口径明确区分：
    - ``turn_total`` 只来自模型循环轮次 ``iteration_count``；
    - ``llm_call_total`` 只来自持久化的 Provider 调用计数 ``llm_call_count``；
    - 工具调用数量来自持久化 ``agent_tool_calls``，不使用前端当前页长度；
    - Observation 的代码证据必须有 location.role=evidence；背景引用不会计入代码证据。
    """
    nodes = list(plan.nodes) if plan is not None else []
    node_completed = sum(
        1
        for node in nodes
        if _status_value(node.status) in _COMPLETED_NODE_STATUSES
    )
    node_failed = sum(
        1 for node in nodes if _status_value(node.status) == AgentPlanNodeStatus.FAILED.value
    )

    tool_query = AgentToolCall.query.filter_by(run_id=run.id)
    tool_total = tool_query.count()
    tool_succeeded = tool_query.filter(
        AgentToolCall.status.in_(_SUCCESSFUL_TOOL_STATUSES)
    ).count()
    tool_failed = tool_query.filter(
        AgentToolCall.status.in_(_FAILED_TOOL_STATUSES)
    ).count()

    observation_query = AgentObservation.query.filter_by(run_id=run.id)
    observation_total = observation_query.count()
    observation_with_code_evidence = (
        observation_query.join(
            AgentObservationLocation,
            AgentObservationLocation.observation_id == AgentObservation.id,
        )
        .filter(AgentObservationLocation.role == "evidence")
        .distinct()
        .count()
    )
    observation_unverified = observation_query.filter(
        AgentObservation.status == "unverified"
    ).count()

    approval_pending = AgentApproval.query.filter_by(
        run_id=run.id,
        status="pending",
    ).count()
    warning_codes = tuple(dict.fromkeys(run.warning_codes or []))


    return {
        "plan_node_total": len(nodes),
        "plan_node_completed": node_completed,
        "plan_node_failed": node_failed,
        "turn_total": int(run.iteration_count or 0),
        "llm_call_total": int(run.llm_call_count or 0),
        "tool_call_total": int(tool_total),
        "tool_call_succeeded": int(tool_succeeded),
        "tool_call_failed": int(tool_failed),
        "observation_total": int(observation_total),
        "observation_with_code_evidence": int(observation_with_code_evidence),
        "observation_unverified": int(observation_unverified),
        "replan_total": int(run.replan_count or 0),
        "approval_pending": int(approval_pending),
        "warning_total": len(warning_codes),
    }


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
