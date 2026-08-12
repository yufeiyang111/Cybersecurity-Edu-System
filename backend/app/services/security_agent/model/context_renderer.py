# -*- coding: utf-8 -*-
"""Context renderer（T04，spec §7.4/§10.5）：Fallback 文本渲染与 Tool Result 回填。

- render_fallback_prompt：把 AgentModelRequest 渲染为受限文本 prompt，
  只携带脱敏后的工具描述与消息历史；
- append_tool_results：把 Tool Result Envelope 以 role=tool 消息回填到
  下一次模型请求，必须携带正确 tool_call_id。
"""
from __future__ import annotations

import json

from app.services.security_agent.model.action_parser import ACTION_SCHEMA_VERSION
from app.services.security_agent.model.contracts import (
    AgentModelMessage,
    AgentModelRequest,
)

# Tool Result Envelope 允许字段（spec §10.5），模型只收受限摘要
TOOL_RESULT_ENVELOPE_KEYS = (
    "call_id",
    "tool_name",
    "status",
    "summary",
    "structured",
    "artifact_refs",
    "warning_codes",
    "error_code",
    "retryable",
    "truncated",
)


def render_fallback_prompt(request: AgentModelRequest) -> str:
    """把 Agent 请求渲染为 Fallback 文本 prompt（严格 schema 指令）。"""
    message_lines: list[str] = []
    for message in request.messages:
        if message.role == "tool":
            line = f"tool({message.tool_call_id}): {message.content or ''}"
        elif message.content:
            line = f"{message.role}: {message.content}"
        elif message.tool_calls:
            names = ", ".join(call.name for call in message.tool_calls)
            line = f"assistant: 调用工具 [{names}]"
        else:
            continue
        message_lines.append(line)

    tool_lines = "\n".join(
        f"- {tool.name}: {tool.description}" for tool in request.tools
    )
    return (
        "你是 CyberGuard 安全审查 Agent。基于以下消息与可用工具，"
        f"只输出 Action Envelope JSON（schema v{ACTION_SCHEMA_VERSION}）：\n"
        '格式：{"action": "tool_calls" | "final_answer", "payload": {...}}\n'
        "tool_calls.payload.tool_calls 每项只允许字段 id/name/arguments。\n\n"
        f"可用工具：\n{tool_lines or '（无）'}\n\n"
        f"消息历史：\n{chr(10).join(message_lines) or '（空）'}"
    )


def append_tool_results(
    messages: tuple[AgentModelMessage, ...],
    results: list[dict],
) -> tuple[AgentModelMessage, ...]:
    """把工具结果回填为 role=tool 消息；无 call_id 的结果直接拒绝。"""
    next_messages = list(messages)
    for result in results:
        call_id = result.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("Tool Result 必须携带非空 call_id 才能回填")
        envelope = {
            key: result.get(key)
            for key in TOOL_RESULT_ENVELOPE_KEYS
            if key in result
        }
        next_messages.append(
            AgentModelMessage(
                role="tool",
                content=json.dumps(envelope, ensure_ascii=False),
                tool_call_id=call_id,
            )
        )
    return tuple(next_messages)
