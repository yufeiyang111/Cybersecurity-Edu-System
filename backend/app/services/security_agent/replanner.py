# -*- coding: utf-8 -*-
"""Replanner：基于证据与用户方向创建新计划版本（A5）。

- 新版本复制上一版全部节点与边（状态保留：已完成节点由 checkpoint 跳过、
  失败节点保持失败不重试），再追加新节点。
- 创建后更新 run.plan_version / replan_count，写决策记录并发出
  plan.replanned / strategy.switched / decision.recorded 事件。
- 硬限制：max_replans、max_plan_nodes、同一 reason_code 触发次数；
  达到限制时返回 None 并发出 AGENT_REPLAN_LIMIT_REACHED 警告（不静默）。
"""
from __future__ import annotations

import logging

from flask import current_app

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanEdge,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentRun,
)
from app.services.security_agent.contracts import (
    EVENT_PLAN_REPLANNED,
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.decision_records import DecisionRecords
from app.services.security_agent.event_service import EventService
from app.services.security_agent.strategy_catalog import NodeSpec

logger = logging.getLogger(__name__)

DEFAULT_MAX_REPLANS = 2
DEFAULT_MAX_PLAN_NODES = 20
DEFAULT_MAX_SAME_FAILURE_ROUTE = 2


class ReplanLimitReached(Exception):
    """重规划达到硬限制；调用方应停止本轮 replan（不是 worker 崩溃）。"""


class Replanner:
    def __init__(self, events: EventService, decisions: DecisionRecords | None = None) -> None:
        self._events = events
        self._decisions = decisions or DecisionRecords(events)

    # ------------------------------------------------------------------ public

    def create_version(
        self,
        run: AgentRun,
        supersedes: AgentPlan,
        *,
        reason_code: str,
        decision_type: str,
        node_specs: tuple[NodeSpec, ...],
        decision_summary: str = "",
        trace_id: str | None = None,
    ) -> AgentPlan | None:
        """创建新计划版本；达到硬限制时返回 None（并发警告事件）。"""
        if not self._limits_allow(run, supersedes, reason_code, trace_id):
            return None

        new_version = supersedes.plan_version + 1
        plan = AgentPlan(
            run_id=run.id,
            plan_version=new_version,
            planner_source=run.planner_source or "rule_based_policy",
            objective=supersedes.objective,
            decision_summary=decision_summary or supersedes.decision_summary,
            hypotheses_json=supersedes.hypotheses_json or [],
            completion_criteria_json=supersedes.completion_criteria_json or [],
        )
        db.session.add(plan)
        db.session.flush()

        existing_keys: set[str] = set()
        for node in supersedes.nodes:
            existing_keys.add(node.node_key)
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=node.node_key,
                    node_type=node.node_type,
                    status=node.status,
                    title=node.title,
                    description=node.description,
                    tool_name=node.tool_name,
                    input_json=node.input_json,
                    depends_on_json=node.depends_on_json,
                    input_artifact_refs=node.input_artifact_refs,
                    output_artifact_refs=node.output_artifact_refs,
                    retry_count=node.retry_count,
                )
            )
        for edge in supersedes.edges:
            db.session.add(
                AgentPlanEdge(
                    plan_id=plan.id,
                    from_node=edge.from_node,
                    to_node=edge.to_node,
                    edge_type=edge.edge_type,
                    condition_json=edge.condition_json,
                )
            )
        db.session.flush()

        added: list[AgentPlanNode] = []
        for spec in node_specs:
            if spec.key in existing_keys:
                continue
            depends = [key for key in spec.depends_on if key in existing_keys] or None
            node = AgentPlanNode(
                plan_id=plan.id,
                node_key=spec.key,
                node_type=spec.node_type,
                status=AgentPlanNodeStatus.PENDING.value,
                title=spec.title,
                description=spec.description,
                tool_name=spec.tool_name,
                input_json=spec.input or None,
                depends_on_json=depends,
            )
            db.session.add(node)
            added.append(node)
            existing_keys.add(spec.key)
            if depends:
                db.session.add(
                    AgentPlanEdge(
                        plan_id=plan.id,
                        from_node=depends[0],
                        to_node=spec.key,
                        edge_type=AgentPlanEdgeType.SUCCESS.value,
                    )
                )
        db.session.flush()

        if added:
            added[0].status = AgentPlanNodeStatus.READY.value

        run.plan_version = plan.plan_version
        run.replan_count = (run.replan_count or 0) + 1
        self._decisions.record(
            run,
            plan_version=plan.plan_version,
            supersedes_version=supersedes.plan_version,
            reason_code=reason_code,
            decision_type=decision_type,
            detail={
                "decision_summary": decision_summary,
                "new_nodes": [node.node_key for node in added],
            },
            trace_id=trace_id,
        )
        self._events.emit(
            run,
            EVENT_PLAN_REPLANNED,
            {
                "plan_id": plan.id,
                "plan_version": plan.plan_version,
                "supersedes_version": supersedes.plan_version,
                "reason_code": reason_code,
                "decision_type": decision_type,
                "new_nodes": [node.node_key for node in added],
                "decision_summary": decision_summary,
            },
            trace_id=trace_id,
        )
        db.session.commit()
        return plan

    # ------------------------------------------------------------------ limits

    def _limits_allow(
        self,
        run: AgentRun,
        supersedes: AgentPlan,
        reason_code: str,
        trace_id: str | None,
    ) -> bool:
        max_replans = _config_int("AGENT_MAX_REPLANS", DEFAULT_MAX_REPLANS)
        if (run.replan_count or 0) >= max_replans:
            self._raise_limit(run, "AGENT_REPLAN_LIMIT_REACHED", "重规划次数已达上限", trace_id)
            return False

        max_same_route = _config_int(
            "AGENT_MAX_SAME_FAILURE_ROUTE", DEFAULT_MAX_SAME_FAILURE_ROUTE
        )
        if self._decisions.count_by_reason(run.id, reason_code) >= max_same_route:
            self._raise_limit(
                run,
                "AGENT_REPLAN_LIMIT_REACHED",
                f"同一决策路线 {reason_code} 触发次数已达上限",
                trace_id,
            )
            return False

        max_nodes = _config_int("AGENT_MAX_PLAN_NODES", DEFAULT_MAX_PLAN_NODES)
        if len(supersedes.nodes) >= max_nodes:
            self._raise_limit(
                run,
                "AGENT_REPLAN_LIMIT_REACHED",
                f"计划节点数已达上限（{max_nodes}）",
                trace_id,
            )
            return False
        return True

    def _raise_limit(self, run: AgentRun, code: str, reason: str, trace_id: str | None) -> None:
        logger.warning("Replan limit reached (run_id=%s, %s)", run.id, reason)
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": [code], "reason": reason},
            trace_id=trace_id,
        )


def _config_int(key: str, default: int) -> int:
    if current_app is None:
        return default
    value = current_app.config.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
