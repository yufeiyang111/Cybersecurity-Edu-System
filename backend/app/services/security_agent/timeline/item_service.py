# -*- coding: utf-8 -*-
"""Timeline ItemService（T03，spec §13.4）：Item 生命周期的幂等写入口。

start / append_delta / complete / fail 每次操作在同一事务内完成：
Item 状态变更 + v2 Event 写入 + run 水位递增，失败可整体回滚；
终态（completed/failed）后拒绝新 delta；dedupe_key 保证重复投递幂等。
"""
from __future__ import annotations

from datetime import datetime

from app import db
from app.models.agent_items import AgentItem
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter

_TERMINAL_ITEM_STATUSES = frozenset({"completed", "failed"})


class ItemStateError(ValueError):
    """Item 生命周期非法：终态后继续 delta 或重复终态转换。"""


class ItemService:
    """T10：单条 delta 大小上限（安全合并留待客户端，语义顺序不变）。"""

    MAX_DELTA_CHARS = 12000
    def __init__(self, writer: EventWriter | None = None) -> None:
        self._writer = writer or EventWriter()

    # ---------------------------------------------------------------- lifecycle

    def start(
        self,
        run: AgentRun,
        *,
        public_id: str,
        item_type: str,
        event_type: str,
        iteration: int = 0,
        parent_item_id: str | None = None,
        conversation_id: int | None = None,
        turn_id: int | None = None,
        sensitive_level: str = "internal",
        summary_json: dict | None = None,
        dedupe_key: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[AgentItem, AgentEvent]:
        if dedupe_key:
            existing = (
                AgentEvent.query.filter_by(run_id=run.id, dedupe_key=dedupe_key)
                .order_by(AgentEvent.id.asc())
                .first()
            )
            if existing is not None and existing.item_public_id:
                return self._require_item(run.id, existing.item_public_id), existing
        item = AgentItem(
            public_id=public_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            run_id=run.id,
            iteration=iteration,
            item_type=item_type,
            status="started",
            parent_item_id=parent_item_id,
            summary_json=summary_json,
            sensitive_level=sensitive_level,
            started_at=datetime.utcnow(),
        )
        db.session.add(item)
        db.session.flush()
        event = self._writer.emit(
            run,
            event_type=event_type,
            item_id=public_id,
            parent_item_id=parent_item_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            iteration=iteration,
            dedupe_key=dedupe_key,
            trace_id=trace_id,
        )
        return item, event

    def append_delta(
        self,
        run: AgentRun,
        public_id: str,
        *,
        delta: str,
        event_type: str,
        iteration: int | None = None,
        trace_id: str | None = None,
    ) -> tuple[AgentItem, AgentEvent]:
        item = self._require_item(run.id, public_id)
        if item.status in _TERMINAL_ITEM_STATUSES:
            raise ItemStateError(
                f"Item {public_id} 已处于终态 {item.status}，拒绝追加 delta"
            )
        if not isinstance(delta, str):
            raise ItemStateError("delta 必须是字符串")
        if len(delta) > self.MAX_DELTA_CHARS:
            raise ItemStateError(
                f"delta 超过单条上限 {self.MAX_DELTA_CHARS} 字符"
            )
        item.content_redacted = (item.content_redacted or "") + delta
        event = self._writer.emit(
            run,
            event_type=event_type,
            item_id=public_id,
            iteration=item.iteration if iteration is None else iteration,
            payload={"delta": delta, "sensitive_level": item.sensitive_level},
            trace_id=trace_id,
        )
        return item, event

    def complete(
        self,
        run: AgentRun,
        public_id: str,
        *,
        content: str | None = None,
        summary_json: dict | None = None,
        event_type: str,
        trace_id: str | None = None,
    ) -> tuple[AgentItem, AgentEvent]:
        item = self._require_item(run.id, public_id)
        self._ensure_not_terminal(item)
        if content is not None:
            item.content_redacted = content
        if summary_json is not None:
            item.summary_json = summary_json
        item.status = "completed"
        item.completed_at = datetime.utcnow()
        event = self._writer.emit(
            run,
            event_type=event_type,
            item_id=public_id,
            iteration=item.iteration,
            trace_id=trace_id,
        )
        return item, event

    def fail(
        self,
        run: AgentRun,
        public_id: str,
        *,
        error_code: str,
        event_type: str,
        trace_id: str | None = None,
    ) -> tuple[AgentItem, AgentEvent]:
        item = self._require_item(run.id, public_id)
        self._ensure_not_terminal(item)
        item.status = "failed"
        item.completed_at = datetime.utcnow()
        item.summary_json = {
            **(item.summary_json or {}),
            "error_code": error_code,
        }
        event = self._writer.emit(
            run,
            event_type=event_type,
            item_id=public_id,
            iteration=item.iteration,
            payload={"error_code": error_code},
            trace_id=trace_id,
        )
        return item, event

    # ---------------------------------------------------------------- helpers

    def _require_item(self, run_id: int, public_id: str) -> AgentItem:
        item = AgentItem.query.filter_by(run_id=run_id, public_id=public_id).first()
        if item is None:
            raise ItemStateError(f"Item 不存在：run={run_id} public_id={public_id}")
        return item

    @staticmethod
    def _ensure_not_terminal(item: AgentItem) -> None:
        if item.status in _TERMINAL_ITEM_STATUSES:
            raise ItemStateError(
                f"Item {item.public_id} 已处于终态 {item.status}"
            )
