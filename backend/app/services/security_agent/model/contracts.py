# -*- coding: utf-8 -*-
"""Agent 模型网关契约（T01，spec §7.1-§7.3，v1.1 Reasoning Summary）。

保留旧文本型 LLMRequest/LLMResponse 不动；Agent 专用契约新增于此，
Provider 路由与 Tool Calling 适配（T04）只消费这些类型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.llm.redactor import redact_reasoning

_AGENT_ROLES = frozenset({"system", "user", "assistant", "tool"})


class ContractValidationError(ValueError):
    """Agent 契约非法：消息、动作、流事件或推理摘要违反冻结边界。"""


class AgentStreamEventType(str, Enum):
    OUTPUT_TEXT_DELTA = "output_text_delta"
    DECISION_SUMMARY_DELTA = "decision_summary_delta"
    REASONING_SUMMARY_DELTA = "reasoning_summary_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_ARGUMENTS_DELTA = "tool_call_arguments_delta"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    USAGE = "usage"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class AgentModelToolCall:
    """Provider 原生或 JSON Fallback 标准化后的单次工具调用。"""

    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentModelMessage:
    role: str
    content: str | None = None
    tool_calls: tuple[AgentModelToolCall, ...] = ()
    tool_call_id: str | None = None
    reasoning_content: str | None = None

    def __post_init__(self) -> None:
        if self.role not in _AGENT_ROLES:
            raise ContractValidationError(f"非法消息角色：{self.role}")
        if self.role == "tool" and not self.tool_call_id:
            raise ContractValidationError("tool 消息必须携带 tool_call_id")


@dataclass(frozen=True)
class AgentToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentModelRequest:
    messages: tuple[AgentModelMessage, ...]
    tools: tuple[AgentToolDefinition, ...] = ()
    tool_choice: str | dict | None = None
    temperature: float = 0.3
    max_tokens: int = 1200
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.messages:
            raise ContractValidationError("messages 不能为空")
        if not 0 <= self.temperature <= 1:
            raise ContractValidationError("temperature 必须在 0 到 1 之间")
        if (
            not isinstance(self.max_tokens, int)
            or isinstance(self.max_tokens, bool)
            or self.max_tokens <= 0
        ):
            raise ContractValidationError("max_tokens 必须是正整数")


@dataclass(frozen=True)
class AgentModelResponse:
    content: str | None
    tool_calls: tuple[AgentModelToolCall, ...]
    finish_reason: str | None
    provider_name: str
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    warning_code: str | None = None
    reasoning_content: str | None = None
    action_kind: str | None = None
    action_payload: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """互斥动作校验：一轮不得同时提交最终回答与工具调用。"""
        if self.content and self.tool_calls:
            raise ContractValidationError("一轮不能同时提交最终回答与工具调用")
        if self.action_kind is not None and (self.content or self.tool_calls):
            raise ContractValidationError("结构化动作不得与文本/工具调用混用")

    def to_action(self):
        """把响应转换为标准 AgentAction（tool_calls 先按单调用拆分）。"""
        from app.services.security_agent.loop.actions import (
            ActionKind,
            AgentAction,
            AskUserAction,
            FinalAnswerAction,
            PlanUpdateAction,
            RequestApprovalAction,
            ToolCallAction,
        )

        self.validate()
        if self.action_kind is not None:
            payload = self.action_payload or {}
            if self.action_kind == ActionKind.REQUEST_APPROVAL.value:
                return AgentAction(
                    kind=ActionKind.REQUEST_APPROVAL,
                    action=RequestApprovalAction.from_dict(payload),
                )
            if self.action_kind == ActionKind.ASK_USER.value:
                return AgentAction(
                    kind=ActionKind.ASK_USER,
                    action=AskUserAction.from_dict(payload),
                )
            if self.action_kind == ActionKind.PLAN_UPDATE.value:
                return AgentAction(
                    kind=ActionKind.PLAN_UPDATE,
                    action=PlanUpdateAction.from_dict(payload),
                )
            raise ContractValidationError(f"未知结构化动作：{self.action_kind}")
        if self.content:
            return AgentAction(
                kind=ActionKind.FINAL_ANSWER,
                action=FinalAnswerAction(content=self.content),
            )
        if self.tool_calls:
            if len(self.tool_calls) != 1:
                raise ContractValidationError(
                    "工具调用动作必须逐轮单调用执行，多个调用先拆"
                )
            call = self.tool_calls[0]
            return AgentAction(
                kind=ActionKind.TOOL_CALLS,
                action=ToolCallAction(
                    call_id=call.call_id,
                    name=call.name,
                    arguments=call.arguments,
                ),
            )
        raise ContractValidationError("响应既无文本也无工具调用")


@dataclass(frozen=True)
class AgentModelStreamEvent:
    event_type: str
    item_id: str | None = None
    call_id: str | None = None
    delta: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            AgentStreamEventType(self.event_type)
        except ValueError:
            raise ContractValidationError(f"未知流事件类型：{self.event_type}")


@dataclass(frozen=True)
class ProviderCapabilities:
    """Provider 能力协商（T04 使用），默认全部关闭、绝不乐观假设。"""

    supports_native_tools: bool = False
    supports_streaming: bool = False
    supports_parallel_tool_calls: bool = False
    supports_reasoning_tokens_usage: bool = False
    supports_reasoning_channel: bool = False
    max_context_tokens: int = 0
    max_output_tokens: int = 0
    supports_json_schema: bool = False


@dataclass(frozen=True)
class ReasoningSummary:
    """受限推理摘要（v1.1）：模型真实 reasoning 输出的脱敏限长快照。

    不是伪造文案，也不是完整原始思维链全文；入库/入 SSE 前必须通过
    redact_reasoning 门禁（原始全文只允许在进程内瞬时累积）。
    """

    source_channel: str
    redacted_text: str
    max_chars: int
    sensitive_level: str

    def __post_init__(self) -> None:
        if not isinstance(self.redacted_text, str):
            raise ContractValidationError("redacted_text 必须是字符串")
        if len(self.redacted_text) > self.max_chars:
            raise ContractValidationError(f"推理摘要超过上限 {self.max_chars} 字符")
        if not self.sensitive_level:
            raise ContractValidationError("推理摘要必须标注 sensitive_level")
        redacted = redact_reasoning(self.redacted_text)
        if redacted is None or redacted != self.redacted_text:
            raise ContractValidationError("推理摘要未通过脱敏门禁：包含敏感内容")

    def to_dict(self) -> dict:
        return {
            "source_channel": self.source_channel,
            "redacted_text": self.redacted_text,
            "max_chars": self.max_chars,
            "sensitive_level": self.sensitive_level,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "ReasoningSummary":
        if not isinstance(raw, dict):
            raise ContractValidationError("ReasoningSummary 必须是对象")
        try:
            return cls(
                source_channel=str(raw["source_channel"]),
                redacted_text=str(raw["redacted_text"]),
                max_chars=int(raw["max_chars"]),
                sensitive_level=str(raw["sensitive_level"]),
            )
        except KeyError as exc:
            raise ContractValidationError(
                f"ReasoningSummary 缺少字段：{exc.args[0]}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("ReasoningSummary 字段类型非法") from exc
