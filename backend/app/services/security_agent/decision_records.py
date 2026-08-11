# -*- coding: utf-8 -*-
"""决策记录（Decision Records）：重规划决策的持久化与查询（A5）。

每次 replan / 用户方向追加写一条 agent_decision_records，同时发出
strategy.switched 与 decision.recorded 事件；前端决策时间线据此渲染。
"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import AgentDecisionRecord, AgentRun
from app.services.agent_observability import AgentLogger
from app.services.security_agent.contracts import (
    EVENT_DECISION_RECORDED,
    EVENT_STRATEGY_SWITCHED,
)
from app.services.security_agent.event_service import EventService


class DecisionRecords:
    def __init__(self, events: EventService) -> None:
        self._events = events
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ write

    def record(
        self,
        run: AgentRun,
        *,
        plan_version: int,
        supersedes_version: int | None,
        reason_code: str,
        decision_type: str,
        detail: dict | None = None,
        trace_id: str | None = None,
    ) -> AgentDecisionRecord:
        record = AgentDecisionRecord(
            run_id=run.id,
            plan_version=plan_version,
            supersedes_version=supersedes_version,
            reason_code=reason_code,
            decision_type=decision_type,
            detail_json=detail or {},
        )
        db.session.add(record)
        db.session.flush()
        self._events.emit(
            run,
            EVENT_DECISION_RECORDED,
            {
                "decision_id": record.id,
                "plan_version": plan_version,
                "supersedes_version": supersedes_version,
                "reason_code": reason_code,
                "decision_type": decision_type,
                "detail": record.detail_json or {},
            },
            trace_id=trace_id,
        )
        self._events.emit(
            run,
            EVENT_STRATEGY_SWITCHED,
            {
                "decision_id": record.id,
                "reason_code": reason_code,
                "from_plan_version": supersedes_version,
                "to_plan_version": plan_version,
                "decision_summary": (detail or {}).get("decision_summary", ""),
            },
            trace_id=trace_id,
        )
        self._agent_log.plan_replanned(
            run,
            reason_code=reason_code,
            plan_version=plan_version,
            supersedes_version=supersedes_version,
            decision_type=decision_type,
            trace_id=trace_id,
        )
        return record

    # ------------------------------------------------------------------ read

    def list_for_run(self, run_id: int, *, limit: int = 50) -> list[AgentDecisionRecord]:
        return (
            AgentDecisionRecord.query.filter_by(run_id=run_id)
            .order_by(AgentDecisionRecord.id.desc())
            .limit(limit)
            .all()
        )

    def count_by_reason(self, run_id: int, reason_code: str) -> int:
        return (
            AgentDecisionRecord.query.filter_by(run_id=run_id, reason_code=reason_code)
            .count()
        )


def get_decision_records(events: EventService | None = None) -> DecisionRecords:
    return DecisionRecords(events or EventService())
