# -*- coding: utf-8 -*-
"""Harness V3 假设规划提示词：仅允许选择固定技能与扫描位置索引。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

PROMPT_TEMPLATE_VERSION = "hypothesis_planner_v1"

_SYSTEM_PROMPT = (
    "你是 CyberGuard 安全审计的受限假设规划器。"
    "你只能从输入中给出的审计技能 key 中选择，并且只能引用给出的扫描位置索引。"
    "不要创建新技能、工具、文件范围或证据条件；不要输出源码、提示词或推理过程。"
    "只输出严格 JSON："
    '{"hypotheses":[{"skill_key":"固定技能 key","scope_indices":[0],"priority":1}]}'
)


def build_hypothesis_planner_prompt(
    *,
    skills: Iterable[object],
    finding_signals: Iterable[object],
    max_hypotheses: int,
) -> dict:
    """构造不携带源码文本的受限规划输入。"""
    skill_rows = [
        {
            "key": str(getattr(skill, "key", "")),
            "required_evidence": list(getattr(skill, "required_evidence", ()) or ()),
        }
        for skill in skills
    ]
    signal_rows = []
    for index, signal in enumerate(finding_signals):
        signal_rows.append(
            {
                "index": index,
                "file_path": str(getattr(signal, "file_path", "") or ""),
                "start_line": _safe_line(getattr(signal, "start_line", None)),
                "end_line": _safe_line(getattr(signal, "end_line", None)),
                "severity": str(getattr(signal, "severity", "") or ""),
                "rule_id": str(getattr(signal, "rule_id", "") or ""),
                "category": str(getattr(signal, "category", "") or ""),
                "cwe_id": str(getattr(signal, "cwe_id", "") or ""),
            }
        )
    user_prompt = (
        f"最多输出 {max_hypotheses} 条假设。\n"
        f"固定审计技能：{json.dumps(skill_rows, ensure_ascii=False)}\n"
        f"确定性扫描位置（仅元数据，不含源码）：{json.dumps(signal_rows, ensure_ascii=False)}\n"
        "每条假设至少选择一个 scope_indices；priority 必须为 1 到 100 的整数。"
    )
    return {
        "system_prompt": _SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "max_tokens": 1200,
    }


def parse_hypothesis_plan(text: str) -> dict:
    """解析模型返回的 JSON；不接受非对象输出。"""
    if not text:
        raise ValueError("假设规划输出为空")
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("假设规划输出缺少 JSON 对象")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"假设规划 JSON 解析失败：{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("假设规划输出必须是 JSON 对象")
    return parsed


def prompt_digest(text: str) -> str:
    """只记录摘要，避免把 Provider 输入写入运行时数据。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _safe_line(value: object) -> int | None:
    try:
        line = int(value)
    except (TypeError, ValueError):
        return None
    return line if line > 0 else None
