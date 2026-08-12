# -*- coding: utf-8 -*-
"""Timeline serializers（T03，spec §14.4）：v1 → Legacy Item 只读兼容。

旧 AgentMessage / AgentEvent 转换为 schema_version=1 的 Legacy Item，
保留原始来源与顺序，不伪造 v2 水位与 iteration。
"""
from __future__ import annotations

from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentMessage


def legacy_item_from_message(message: AgentMessage) -> dict:
    """旧消息 → legacy item（assistant_message / user_message）。"""
    return {
        "public_id": f"legacy-msg-{message.id}",
        "item_type": (
            "assistant_message" if message.role == "agent" else "user_message"
        ),
        "schema_version": 1,
        "status": "completed",
        "content": message.content or "",
        "occurred_at": message.created_at.isoformat()
        if message.created_at
        else None,
        "source": "legacy_message",
    }


def legacy_item_from_event(event: AgentEvent) -> dict:
    """旧事件 → legacy item，保留原始 sequence。"""
    return {
        "public_id": f"legacy-ev-{event.id}",
        "sequence": event.sequence,
        "schema_version": 1,
        "event_type": event.event_type,
        "status": "completed",
        "payload": event.payload_json or {},
        "occurred_at": event.occurred_at.isoformat()
        if event.occurred_at
        else None,
        "source": "legacy_event",
    }
