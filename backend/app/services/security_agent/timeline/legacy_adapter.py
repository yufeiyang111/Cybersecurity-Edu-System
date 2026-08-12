# -*- coding: utf-8 -*-
"""Legacy adapter（T12，spec §14.4）：v1 数据 → legacy item 只读兼容。

- 旧 AgentMessage / AgentEvent 转换为 schema_version=1 的 Legacy Item；
- 保留原始来源与顺序，不伪造 v2 水位与 iteration；
- 新 v2 Run 不双写旧表，旧字段由本模块派生。
"""
from __future__ import annotations

from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentMessage
from app.services.security_agent.timeline.serializers import (
    legacy_item_from_event,
    legacy_item_from_message,
)


def build_legacy_items(run_id: int) -> list[dict]:
    """把一个 run 的 v1 数据转换为 Legacy Items（保持原始顺序）。"""
    items: list[dict] = []
    messages = (
        AgentMessage.query.filter_by(run_id=run_id)
        .order_by(AgentMessage.id.asc())
        .all()
    )
    events = (
        AgentEvent.query.filter_by(run_id=run_id)
        .order_by(AgentEvent.sequence.asc())
        .all()
    )
    for message in messages:
        items.append(legacy_item_from_message(message))
    for event in events:
        items.append(legacy_item_from_event(event))
    return items
