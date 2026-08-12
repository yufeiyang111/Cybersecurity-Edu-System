# -*- coding: utf-8 -*-
"""Timeline EventWriter（T03，spec §13.5）：v2 Event 的唯一写入口。

序列分配使用原子策略：UPDATE agent_runs SET last_event_sequence =
last_event_sequence + 1 在同事务内持有行锁，禁止无锁 MAX(sequence)+1；
MySQL 与文件型 SQLite 均满足（SQLite 依赖文件写锁，由短事务保证）。
"""
from __future__ import annotations

from sqlalchemy import update

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.contracts import (
    AGENT_EVENT_V2_TYPES,
    EVENT_SCHEMA_VERSION_V2,
)


class EventWriter:
    """原子分配 sequence 并持久化 v2 Event；业务模块禁止自行 add(AgentEvent)。"""

    def next_sequence(self, run: AgentRun) -> int:
        """原子递增 run 的 last_event_sequence 并返回新值（行锁语义）。"""
        db.session.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(last_event_sequence=AgentRun.last_event_sequence + 1)
        )
        db.session.refresh(run, attribute_names=["last_event_sequence"])
        return int(run.last_event_sequence)

    def emit(
        self,
        run: AgentRun,
        *,
        event_type: str,
        payload: dict | None = None,
        trace_id: str | None = None,
        iteration: int = 0,
        item_id: str | None = None,
        parent_item_id: str | None = None,
        conversation_id: int | None = None,
        turn_id: int | None = None,
        state_version: int | None = None,
        dedupe_key: str | None = None,
    ) -> AgentEvent:
        if event_type not in AGENT_EVENT_V2_TYPES:
            raise ValueError(f"未知 v2 事件类型：{event_type}")
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("payload 必须是对象")
        sequence = self.next_sequence(run)
        event = AgentEvent(
            run_id=run.id,
            sequence=sequence,
            state_version=(
                run.state_version if state_version is None else state_version
            ),
            event_type=event_type,
            schema_version=EVENT_SCHEMA_VERSION_V2,
            trace_id=trace_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            iteration=iteration,
            item_public_id=item_id,
            parent_item_public_id=parent_item_id,
            dedupe_key=dedupe_key,
            payload_json=payload or {},
        )
        db.session.add(event)
        return event
