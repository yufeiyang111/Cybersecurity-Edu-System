# -*- coding: utf-8 -*-
"""Timeline 契约（T01，spec §13.1-§13.3，v1.1 Reasoning Summary）。

Event Envelope v2 是数据库、Snapshot、SSE 与前端共用的单一事实源格式；
Item 类型与事件类型在此冻结，业务模块不得各自发明。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.llm.redactor import redact_reasoning
from app.services.security_agent.loop.policy import REASONING_SUMMARY_MAX_CHARS

EVENT_SCHEMA_VERSION_V2 = 2

AGENT_REASONING_RAW_REJECTED = "AGENT_REASONING_RAW_REJECTED"

_RAW_REASONING_KEYS = frozenset(
    {"raw_reasoning", "chain_of_thought", "raw_cot", "reasoning_full", "reasoning_raw"}
)
_REASONING_KEYS = frozenset({"reasoning", "reasoning_delta"})


class ItemType(str, Enum):
    USER_MESSAGE = "user_message"
    INTENT_SUMMARY = "intent_summary"
    PLAN = "plan"
    DECISION_SUMMARY = "decision_summary"
    REASONING_SUMMARY = "reasoning_summary"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    OBSERVATION = "observation"
    APPROVAL = "approval"
    ASSISTANT_MESSAGE = "assistant_message"
    CONTROLLER_FEEDBACK = "controller_feedback"
    WARNING = "warning"


EVENT_RUN_CREATED = "run.created"
EVENT_RUN_STATE_CHANGED = "run.state.changed"
EVENT_RUN_COMPLETED = "run.completed"
EVENT_RUN_FAILED = "run.failed"
EVENT_RUN_CANCELED = "run.canceled"
EVENT_USER_MESSAGE_CREATED = "item.user_message.created"
EVENT_INTENT_COMPLETED = "item.intent.completed"
EVENT_PLAN_CREATED = "item.plan.created"
EVENT_PLAN_UPDATED = "item.plan.updated"
EVENT_DECISION_CREATED = "item.decision.created"
EVENT_REASONING_SUMMARY_STARTED = "item.reasoning_summary.started"
EVENT_REASONING_SUMMARY_DELTA = "item.reasoning_summary.delta"
EVENT_REASONING_SUMMARY_COMPLETED = "item.reasoning_summary.completed"
EVENT_REASONING_SUMMARY_FAILED = "item.reasoning_summary.failed"
EVENT_TOOL_CALL_STARTED = "item.tool_call.started"
EVENT_TOOL_CALL_COMPLETED = "item.tool_call.completed"
EVENT_TOOL_CALL_FAILED = "item.tool_call.failed"
EVENT_TOOL_RESULT_CREATED = "item.tool_result.created"
EVENT_OBSERVATION_CREATED = "item.observation.created"
EVENT_APPROVAL_REQUESTED = "item.approval.requested"
EVENT_APPROVAL_RESOLVED = "item.approval.resolved"
EVENT_ASSISTANT_MESSAGE_STARTED = "item.assistant_message.started"
EVENT_ASSISTANT_MESSAGE_DELTA = "item.assistant_message.delta"
EVENT_ASSISTANT_MESSAGE_COMPLETED = "item.assistant_message.completed"
EVENT_ASSISTANT_MESSAGE_FAILED = "item.assistant_message.failed"
EVENT_CONTROLLER_FEEDBACK_CREATED = "item.controller_feedback.created"
EVENT_BUDGET_UPDATED = "budget.updated"
EVENT_STRATEGY_PROVIDER_SWITCHED = "strategy.provider_switched"
EVENT_WARNING_RAISED = "warning.raised"
EVENT_CHECKPOINT_CREATED = "checkpoint.created"
EVENT_HEARTBEAT = "heartbeat"

AGENT_EVENT_V2_TYPES = frozenset(
    {
        EVENT_RUN_CREATED,
        EVENT_RUN_STATE_CHANGED,
        EVENT_RUN_COMPLETED,
        EVENT_RUN_FAILED,
        EVENT_RUN_CANCELED,
        EVENT_USER_MESSAGE_CREATED,
        EVENT_INTENT_COMPLETED,
        EVENT_PLAN_CREATED,
        EVENT_PLAN_UPDATED,
        EVENT_DECISION_CREATED,
        EVENT_REASONING_SUMMARY_STARTED,
        EVENT_REASONING_SUMMARY_DELTA,
        EVENT_REASONING_SUMMARY_COMPLETED,
        EVENT_REASONING_SUMMARY_FAILED,
        EVENT_TOOL_CALL_STARTED,
        EVENT_TOOL_CALL_COMPLETED,
        EVENT_TOOL_CALL_FAILED,
        EVENT_TOOL_RESULT_CREATED,
        EVENT_OBSERVATION_CREATED,
        EVENT_APPROVAL_REQUESTED,
        EVENT_APPROVAL_RESOLVED,
        EVENT_ASSISTANT_MESSAGE_STARTED,
        EVENT_ASSISTANT_MESSAGE_DELTA,
        EVENT_ASSISTANT_MESSAGE_COMPLETED,
        EVENT_ASSISTANT_MESSAGE_FAILED,
        EVENT_CONTROLLER_FEEDBACK_CREATED,
        EVENT_BUDGET_UPDATED,
        EVENT_STRATEGY_PROVIDER_SWITCHED,
        EVENT_WARNING_RAISED,
        EVENT_CHECKPOINT_CREATED,
        EVENT_HEARTBEAT,
    }
)


@dataclass(frozen=True)
class AgentEventEnvelope:
    """Event Envelope v2：唯一事实源格式，schema_version 恒为 2。"""

    event_id: int
    sequence: int
    event_type: str
    run_id: int
    schema_version: int = EVENT_SCHEMA_VERSION_V2
    conversation_id: int | None = None
    turn_id: int | None = None
    iteration: int = 0
    item_id: str | None = None
    parent_item_id: str | None = None
    state_version: int = 0
    occurred_at: str | None = None
    trace_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.payload, dict):
            raise ValueError("payload 必须是对象")
        if self.event_type.startswith("item.reasoning_summary."):
            if not isinstance(self.payload.get("sensitive_level"), str) or not self.payload["sensitive_level"]:
                raise ValueError("item.reasoning_summary.* 事件必须携带 payload.sensitive_level")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "schema_version": self.schema_version,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "run_id": self.run_id,
            "iteration": self.iteration,
            "item_id": self.item_id,
            "parent_item_id": self.parent_item_id,
            "event_type": self.event_type,
            "state_version": self.state_version,
            "occurred_at": self.occurred_at,
            "trace_id": self.trace_id,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "AgentEventEnvelope":
        if not isinstance(raw, dict):
            raise ValueError("事件 Envelope 必须是对象")
        required = ("event_id", "sequence", "run_id", "event_type")
        missing = [name for name in required if raw.get(name) is None]
        if missing:
            raise ValueError(f"事件 Envelope 缺少必填字段：{', '.join(missing)}")
        try:
            return cls(
                event_id=int(raw["event_id"]),
                sequence=int(raw["sequence"]),
                run_id=int(raw["run_id"]),
                event_type=str(raw["event_type"]),
                schema_version=int(raw.get("schema_version") or EVENT_SCHEMA_VERSION_V2),
                conversation_id=raw.get("conversation_id"),
                turn_id=raw.get("turn_id"),
                iteration=int(raw.get("iteration") or 0),
                item_id=raw.get("item_id"),
                parent_item_id=raw.get("parent_item_id"),
                state_version=int(raw.get("state_version") or 0),
                occurred_at=raw.get("occurred_at"),
                trace_id=raw.get("trace_id"),
                payload=raw.get("payload") or {},
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("事件 Envelope 字段类型非法") from exc


def sanitize_persistable_payload(payload: dict) -> tuple[dict, str | None]:
    """持久化前安全门禁（v1.1）：剥离完整原始思维链字段，脱敏 reasoning 字段。

    返回 (cleaned, warning_code)；warning_code 非 None 表示发生过剥离或脱敏，
    调用方必须记录安全告警码 AGENT_REASONING_RAW_REJECTED，不允许静默。
    """
    if not isinstance(payload, dict):
        return {}, AGENT_REASONING_RAW_REJECTED
    cleaned: dict[str, Any] = {}
    warning: str | None = None
    for key, value in payload.items():
        if key in _RAW_REASONING_KEYS:
            warning = AGENT_REASONING_RAW_REJECTED
            continue
        if isinstance(value, dict):
            nested, nested_warning = sanitize_persistable_payload(value)
            cleaned[key] = nested
            if nested_warning:
                warning = nested_warning
            continue
        if key in _REASONING_KEYS and isinstance(value, str):
            redacted = redact_reasoning(value)
            if redacted is None:
                warning = AGENT_REASONING_RAW_REJECTED
                continue
            if redacted != value:
                warning = AGENT_REASONING_RAW_REJECTED
            cleaned[key] = redacted
            continue
        cleaned[key] = value
    return cleaned, warning
