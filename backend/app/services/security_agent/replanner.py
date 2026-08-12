# -*- coding: utf-8 -*-
"""Replanner（A5，T06）：基于证据与用户方向创建新计划版本。

v1.1/T06：创建逻辑委托给 PlanService（版本上限、digest 幂等、Decision Record
与 v2 事件由 PlanService 统一负责）；本模块保留为固定规则 fallback 的入口，
不再是唯一"多轮策略"。
"""
from __future__ import annotations

import logging

from flask import current_app

from app.models.agent_runtime import AgentPlan, AgentRun
from app.services.security_agent.event_service import EventService
from app.services.security_agent.planning.plan_service import (
    DEFAULT_MAX_PLAN_VERSIONS,
    PlanService,
)
from app.services.security_agent.strategy_catalog import NodeSpec

logger = logging.getLogger(__name__)

DEFAULT_MAX_REPLANS = 2
DEFAULT_MAX_PLAN_NODES = 20
DEFAULT_MAX_SAME_FAILURE_ROUTE = 2


class ReplanLimitReached(Exception):
    """重规划达到硬限制；调用方应停止本轮 replan（不是 worker 崩溃）。"""


class Replanner:
    def __init__(self, events: EventService | None = None) -> None:
        self._service = PlanService(events or EventService())

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
        """创建新计划版本（委托 PlanService）；达到硬限制时返回 None。"""
        if not self._limits_allow(run, supersedes, reason_code, trace_id):
            return None
        return self._service.create_version(
            run,
            supersedes,
            node_specs=node_specs,
            reason_code=reason_code,
            decision_type=decision_type,
            decision_summary=decision_summary,
            trace_id=trace_id,
        )

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
            self._service._raise_limit(run, "AGENT_REPLAN_LIMIT_REACHED", trace_id)
            return False

        from app.services.security_agent.decision_records import DecisionRecords

        decisions = DecisionRecords(self._service._events)
        max_same_route = _config_int(
            "AGENT_MAX_SAME_FAILURE_ROUTE", DEFAULT_MAX_SAME_FAILURE_ROUTE
        )
        if decisions.count_by_reason(run.id, reason_code) >= max_same_route:
            self._service._raise_limit(
                run, "AGENT_REPLAN_LIMIT_REACHED", trace_id
            )
            return False

        max_nodes = _config_int("AGENT_MAX_PLAN_NODES", DEFAULT_MAX_PLAN_NODES)
        if len(supersedes.nodes) >= max_nodes:
            self._service._raise_limit(
                run, "AGENT_REPLAN_LIMIT_REACHED", trace_id
            )
            return False
        return True


def _config_int(key: str, default: int) -> int:
    if current_app is None:
        return default
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default
