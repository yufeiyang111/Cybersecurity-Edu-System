# -*- coding: utf-8 -*-
"""Planner prompt template v1: build the LLM planning request and parse envelopes.

Security constraints:
- the model never receives full source code, only snapshot metadata summaries;
- output must be strict JSON matching the PlanEnvelope schema;
- prompt text and raw model responses are never persisted, only digests.
"""
from __future__ import annotations

import hashlib
import json
import re

PROMPT_TEMPLATE_VERSION = "planner-v1"

SYSTEM_PROMPT = (
    "你是 CyberGuard 安全 Agent 的计划器。根据用户目标与确定性工具清单，"
    "生成一个严格 JSON 的 PlanEnvelope。\n"
    "规则：\n"
    "1. 必须包含 inventory 与 baseline_scan 两个强制基线节点，不得省略。\n"
    "2. 只能使用给出的工具与节点类型，不得发明工具。\n"
    "3. 输出必须是合法 JSON 对象本身，不要用 plan_envelope 或其他键包裹，"
    "不要输出任何额外文字或 markdown 代码块。\n"
    "4. decision_summary 用简体中文简述选择这些步骤的原因。\n"
    "JSON 结构：\n"
    '{"objective":"本轮审计目标","hypotheses":["假设1"],'
    '"nodes":[{"key":"inventory","type":"inventory","title":"清点快照文件",'
    '"description":"描述","tool_name":"inventory_snapshot"}],'
    '"edges":[{"from":"inventory","to":"baseline_scan","type":"success"}],'
    '"completion_criteria":["节点完成条件"],"decision_summary":"规划原因"}'
)

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def build_user_prompt(
    *,
    goal: str,
    intent: dict,
    snapshot_summary: dict | None,
    available_tools: list[dict],
    budget: dict | None,
) -> str:
    tools_text = "\n".join(
        f"- {tool['name']}：{tool['description']}" for tool in available_tools
    )
    summary_text = json.dumps(snapshot_summary or {}, ensure_ascii=False)[:2000]
    budget_text = json.dumps(budget or {}, ensure_ascii=False)
    return (
        f"用户目标：{goal[:2000]}\n"
        f"关注点：{json.dumps(intent, ensure_ascii=False)}\n"
        f"快照摘要：{summary_text}\n"
        f"可用工具：\n{tools_text}\n"
        f"运行预算：{budget_text}\n"
        "请只输出 PlanEnvelope JSON。"
    )


def parse_plan_envelope(text: str) -> dict:
    """Parse a PlanEnvelope from provider text; tolerate fenced JSON blocks.

    Some providers wrap the envelope in an outer key ({"plan_envelope": {...}})
    or nest it under "data"; unwrap those before returning the envelope.
    """
    if not text:
        raise ValueError("Planner 返回为空")
    stripped = text.strip()
    block = _JSON_BLOCK_PATTERN.search(stripped)
    if block is not None:
        stripped = block.group(1)
    try:
        envelope = json.loads(stripped)
    except (TypeError, ValueError) as exc:
        raise ValueError("Planner 返回不是合法 JSON") from exc
    if not isinstance(envelope, dict):
        raise ValueError("Planner 返回必须是 JSON 对象")
    for wrapper_key in ("plan_envelope", "envelope", "data"):
        nested = envelope.get(wrapper_key)
        if isinstance(nested, dict) and wrapper_key in envelope:
            return nested
    return envelope


def prompt_digest(text: str) -> str:
    """SHA-256 digest of a prompt/response for audit; original text never stored."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
