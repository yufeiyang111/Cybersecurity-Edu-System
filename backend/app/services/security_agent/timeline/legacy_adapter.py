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


# ---------------------------------------------------------------------------
# v2 → v1 事件翻译（spec §22.3 回滚：关闭 Event v2 后新建 Run 暂停发 v2
# 协议；翻译后的 schema_version=1 事件可被旧前端 reducer 消费）。
# 无对等物的 v2 事件保持原类型，旧前端按未知事件安全忽略（M-08）。

_V2_TO_V1_EVENT_TYPES = {
    "run.created": "run.created",
    "run.state.changed": "run.state_changed",
    "run.completed": "run.completed",
    "run.failed": "run.state_changed",
    "run.canceled": "run.state_changed",
    "item.plan.created": "plan.created",
    "item.plan.updated": "plan.replanned",
    "item.decision.created": "decision.recorded",
    "item.tool_call.started": "tool.started",
    "item.tool_call.completed": "tool.completed",
    "item.tool_call.failed": "tool.failed",
    "item.observation.created": "observation.created",
    "item.approval.requested": "approval.requested",
    "item.approval.resolved": "approval.resolved",
    "item.reasoning_summary.delta": "llm.reasoning_delta",
    "item.assistant_message.completed": "llm.completed",
    "strategy.provider_switched": "strategy.switched",
    "budget.updated": "budget.updated",
    "warning.raised": "warning.raised",
    "heartbeat": "heartbeat",
}

_V1_SCHEMA_VERSION = 1


def translate_v2_event_to_v1(
    *,
    event_type: str,
    payload: dict | None,
    item_public_id: str | None,
    parent_item_public_id: str | None,
) -> tuple[str, dict, str | None, str | None]:
    """把 v2 事件翻译为 v1 事件（类型 + payload 适配），返回 4 元组。

    顺序：(event_type, payload, item_public_id, parent_item_public_id)。
    无翻译映射的事件原样返回（仍降级为 schema_version=1）。
    """
    data = dict(payload or {})
    translated_type = _V2_TO_V1_EVENT_TYPES.get(event_type, event_type)

    if event_type == "run.failed":
        data = {"status": "failed", **data}
    elif event_type == "run.canceled":
        data = {"status": "canceled", **data}
    elif event_type == "item.tool_call.started":
        data = {
            "tool_call_id": item_public_id,
            "tool_name": data.get("name") or item_public_id or "",
            **data,
        }
    elif event_type == "item.tool_call.completed":
        data = {
            "tool_call_id": item_public_id,
            **data,
        }
    elif event_type == "item.tool_call.failed":
        data = {
            "tool_call_id": item_public_id,
            **data,
        }
    elif event_type == "item.reasoning_summary.delta":
        data = {"delta": data.get("delta") or ""}

    return translated_type, data, item_public_id, parent_item_public_id


def final_answer_content_for_v1(run_id: int, item_public_id: str | None) -> str:
    """翻译 item.assistant_message.completed 时取权威全文（llm.completed.analysis）。"""
    if not item_public_id:
        return ""
    from app.models.agent_items import AgentItem

    item = AgentItem.query.filter_by(
        run_id=run_id, public_id=item_public_id
    ).first()
    return (item.content_redacted or "") if item is not None else ""

