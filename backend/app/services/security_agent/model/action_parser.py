# -*- coding: utf-8 -*-
"""Action Envelope 解析器（T04，spec §7.4）：JSON Fallback 的严格解析与一次修复。

只接受冻结的 Action Envelope schema；拒绝 eval、拒绝正则宽松猜测、
拒绝额外字段与未知动作；解析失败由调用方用 repair_prompt 做一次受控修复。
"""
from __future__ import annotations

import json
import re

from app.services.security_agent.model.contracts import (
    AgentModelResponse,
    AgentModelToolCall,
    ContractValidationError,
)

ACTION_SCHEMA_VERSION = 1

_ALLOWED_ACTIONS = frozenset(
    {"tool_calls", "final_answer", "request_approval", "ask_user", "plan_update"}
)
_TOP_LEVEL_FIELDS = frozenset({"action", "payload", "schema_version"})
_TOOL_CALL_FIELDS = frozenset({"id", "name", "arguments"})
_SAFE_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class ActionParseError(ValueError):
    """Envelope 非法：JSON 错误、未知动作、未知字段或缺失必填字段。"""


def _structured_response(action: str, payload: dict) -> AgentModelResponse:
    return AgentModelResponse(
        content=None,
        tool_calls=(),
        finish_reason="stop",
        provider_name="fallback",
        model=None,
        action_kind=action,
        action_payload=payload,
    )


def parse_action_envelope(text: str) -> AgentModelResponse:
    """严格解析 Action Envelope 文本；非法输入一律抛 ActionParseError。"""
    if not isinstance(text, str) or not text.strip():
        raise ActionParseError("输出为空")
    try:
        body = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ActionParseError("输出不是合法 JSON 对象") from exc
    if not isinstance(body, dict):
        raise ActionParseError("Envelope 必须是 JSON 对象")

    extra = set(body) - _TOP_LEVEL_FIELDS
    if extra:
        raise ActionParseError(f"包含额外顶层字段：{', '.join(sorted(extra))}")

    action = body.get("action")
    if action not in _ALLOWED_ACTIONS:
        raise ActionParseError(f"动作未冻结或未知：{action!r}")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise ActionParseError("payload 必须是对象")

    if action == "final_answer":
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ActionParseError("final_answer.content 必须是非空字符串")
        return AgentModelResponse(
            content=content,
            tool_calls=(),
            finish_reason="stop",
            provider_name="fallback",
            model=None,
        )

    if action == "request_approval":
        request_id = payload.get("request_id")
        tool_name = payload.get("tool_name")
        reason = payload.get("reason", "")
        if not isinstance(request_id, str) or not request_id:
            raise ActionParseError("request_approval.request_id 必须是非空字符串")
        if not isinstance(tool_name, str) or not _SAFE_TOOL_NAME.match(tool_name):
            raise ActionParseError(f"request_approval.tool_name 不是合法工具名：{tool_name!r}")
        if not isinstance(reason, str):
            raise ActionParseError("request_approval.reason 必须是字符串")
        extra_fields = set(payload) - {"request_id", "tool_name", "reason"}
        if extra_fields:
            raise ActionParseError(
                f"request_approval 包含未知字段：{', '.join(sorted(extra_fields))}"
            )
        return _structured_response(
            "request_approval",
            {"request_id": request_id, "tool_name": tool_name, "reason": reason},
        )

    if action == "ask_user":
        question = payload.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ActionParseError("ask_user.question 必须是非空字符串")
        extra_fields = set(payload) - {"question"}
        if extra_fields:
            raise ActionParseError(
                f"ask_user 包含未知字段：{', '.join(sorted(extra_fields))}"
            )
        return _structured_response("ask_user", {"question": question})

    if action == "plan_update":
        patch = payload.get("patch")
        if not isinstance(patch, dict):
            raise ActionParseError("plan_update.patch 必须是对象")
        extra_fields = set(payload) - {"patch"}
        if extra_fields:
            raise ActionParseError(
                f"plan_update 包含未知字段：{', '.join(sorted(extra_fields))}"
            )
        return _structured_response("plan_update", {"patch": patch})

    calls = payload.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        raise ActionParseError("tool_calls 必须是非空数组")
    normalized: list[AgentModelToolCall] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            raise ActionParseError(f"tool_calls[{index}] 必须是对象")
        extra_fields = set(call) - _TOOL_CALL_FIELDS
        if extra_fields:
            raise ActionParseError(
                f"tool_calls[{index}] 包含未知字段：{', '.join(sorted(extra_fields))}"
            )
        call_id = call.get("id")
        name = call.get("name")
        arguments = call.get("arguments")
        if not isinstance(call_id, str) or not call_id:
            raise ActionParseError(f"tool_calls[{index}].id 必须是非空字符串")
        if not isinstance(name, str) or not _SAFE_TOOL_NAME.match(name):
            raise ActionParseError(f"tool_calls[{index}].name 不是合法工具名：{name!r}")
        if not isinstance(arguments, dict):
            raise ActionParseError(f"tool_calls[{index}].arguments 必须是对象")
        normalized.append(
            AgentModelToolCall(call_id=call_id, name=name, arguments=arguments)
        )
    return AgentModelResponse(
        content=None,
        tool_calls=tuple(normalized),
        finish_reason="tool_calls",
        provider_name="fallback",
        model=None,
    )


def repair_prompt(failure_reason: str) -> str:
    """一次受控修复提示：说明失败原因并重申 schema，绝不宽松猜测。"""
    return (
        f"上次输出未通过校验（Action Envelope schema v{ACTION_SCHEMA_VERSION}）："
        f"{failure_reason}。请只重新输出符合该 schema 的 JSON 对象，"
        "不要输出任何多余文字或代码块标记。"
    )
