# -*- coding: utf-8 -*-
"""Harness V3 运行期共享查询与枚举归一化。"""
from __future__ import annotations

from app.models.agent_runtime import AgentPlan, AgentPlanNode, AgentStepExecution
from app.services.security_agent.budget import budget_status


def status_value(value: object) -> str:
    """统一读取 SQLAlchemy Enum 或字符串状态。"""
    return str(getattr(value, "value", value) or "")


def mode_value(run) -> str:
    """统一读取 Run mode。"""
    return status_value(getattr(run, "mode", ""))


def latest_plan(run_id: int) -> AgentPlan | None:
    """返回当前 Run 的最新计划版本。"""
    return (
        AgentPlan.query.filter_by(run_id=run_id)
        .order_by(AgentPlan.plan_version.desc(), AgentPlan.id.desc())
        .first()
    )


def plan_node(plan: AgentPlan, node_key: str) -> AgentPlanNode | None:
    """按稳定 node_key 获取计划节点。"""
    for node in plan.nodes:
        if node.node_key == node_key:
            return node
    return None


def next_step_attempt(plan_node_id: int) -> int:
    """为节点创建严格递增的执行尝试编号。"""
    latest = (
        AgentStepExecution.query.filter_by(plan_node_id=plan_node_id)
        .order_by(AgentStepExecution.attempt_number.desc())
        .first()
    )
    return (latest.attempt_number if latest is not None else 0) + 1


def run_budget_exhausted(run) -> bool:
    """复用统一预算策略，而不是在 V3 重新解释各类预算字段。"""
    return bool(budget_status(run).get("exhausted"))
