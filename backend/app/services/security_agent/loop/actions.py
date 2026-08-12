# -*- coding: utf-8 -*-
"""Agent Loop 标准化动作契约（T01，spec §6.4）。

模型每一轮只能返回五种判别动作之一：工具调用、计划更新、请求审批、
询问用户、最终回答；控制器据此决定下一步，禁止自由文本猜测动作。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionKind(str, Enum):
    TOOL_CALLS = "tool_calls"
    PLAN_UPDATE = "plan_update"
    REQUEST_APPROVAL = "request_approval"
    ASK_USER = "ask_user"
    FINAL_ANSWER = "final_answer"


class AgentActionError(ValueError):
    """动作契约非法：未知类型或 payload 与类型不匹配。"""


@dataclass(frozen=True)
class ToolCallAction:
    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": dict(self.arguments),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "ToolCallAction":
        call_id = raw.get("call_id")
        name = raw.get("name")
        arguments = raw.get("arguments")
        if not isinstance(call_id, str) or not call_id:
            raise AgentActionError("tool_calls.call_id 必须是非空字符串")
        if not isinstance(name, str) or not name:
            raise AgentActionError("tool_calls.name 必须是非空字符串")
        if not isinstance(arguments, dict):
            raise AgentActionError("tool_calls.arguments 必须是对象")
        return cls(call_id=call_id, name=name, arguments=arguments)


@dataclass(frozen=True)
class PlanUpdateAction:
    patch: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"patch": dict(self.patch)}

    @classmethod
    def from_dict(cls, raw: dict) -> "PlanUpdateAction":
        patch = raw.get("patch")
        if not isinstance(patch, dict):
            raise AgentActionError("plan_update.patch 必须是对象")
        return cls(patch=patch)


@dataclass(frozen=True)
class RequestApprovalAction:
    request_id: str
    tool_name: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "RequestApprovalAction":
        request_id = raw.get("request_id")
        tool_name = raw.get("tool_name")
        if not isinstance(request_id, str) or not request_id:
            raise AgentActionError("request_approval.request_id 必须是非空字符串")
        if not isinstance(tool_name, str) or not tool_name:
            raise AgentActionError("request_approval.tool_name 必须是非空字符串")
        return cls(
            request_id=request_id,
            tool_name=tool_name,
            reason=str(raw.get("reason") or ""),
        )


@dataclass(frozen=True)
class AskUserAction:
    question: str

    def to_dict(self) -> dict:
        return {"question": self.question}

    @classmethod
    def from_dict(cls, raw: dict) -> "AskUserAction":
        question = raw.get("question")
        if not isinstance(question, str) or not question:
            raise AgentActionError("ask_user.question 必须是非空字符串")
        return cls(question=question)


@dataclass(frozen=True)
class FinalAnswerAction:
    content: str

    def to_dict(self) -> dict:
        return {"content": self.content}

    @classmethod
    def from_dict(cls, raw: dict) -> "FinalAnswerAction":
        content = raw.get("content")
        if not isinstance(content, str) or not content:
            raise AgentActionError("final_answer.content 必须是非空字符串")
        return cls(content=content)


_ACTION_FACTORIES = {
    ActionKind.TOOL_CALLS: ToolCallAction.from_dict,
    ActionKind.PLAN_UPDATE: PlanUpdateAction.from_dict,
    ActionKind.REQUEST_APPROVAL: RequestApprovalAction.from_dict,
    ActionKind.ASK_USER: AskUserAction.from_dict,
    ActionKind.FINAL_ANSWER: FinalAnswerAction.from_dict,
}


@dataclass(frozen=True)
class AgentAction:
    """标准化动作：kind + 单一 payload，杜绝自由文本猜测。"""

    kind: ActionKind
    action: object

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "action": self.action.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "AgentAction":
        if not isinstance(raw, dict):
            raise AgentActionError("AgentAction 必须是对象")
        kind_raw = raw.get("kind")
        payload = raw.get("action")
        if not isinstance(kind_raw, str) or not kind_raw:
            raise AgentActionError("AgentAction.kind 必须是非空字符串")
        try:
            kind = ActionKind(kind_raw)
        except ValueError:
            raise AgentActionError(f"未知 Agent 动作类型：{kind_raw}")
        if not isinstance(payload, dict):
            raise AgentActionError("AgentAction.action 必须是对象")
        factory = _ACTION_FACTORIES[kind]
        try:
            action = factory(payload)
        except AgentActionError:
            raise
        except Exception as exc:
            raise AgentActionError(f"动作 payload 与类型不匹配：{kind_raw}") from exc
        return cls(kind=kind, action=action)
