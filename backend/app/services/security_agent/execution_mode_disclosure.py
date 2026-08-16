# -*- coding: utf-8 -*-
"""Agent 实际执行模式的提示词约束与输出一致性守卫。"""
from __future__ import annotations

import re

from app.models.agent_runtime import AgentRun
from app.services.security_agent.feature_flags import AgentFeatureFlags


_NON_V3_CLAIM_MARKERS = (
    "Harness V3",
    "HarnessV3",
    "V3 验收",
    "V3验证",
    "V3 验证",
    "验收结果",
    "验收标准",
    "攻击路径验证",
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?])|(?<=\n)")


def analysis_execution_instruction(run: AgentRun) -> str:
    """返回不可被用户目标覆盖的实际执行模式约束。"""
    if AgentFeatureFlags().for_run(run).harness_v3:
        return (
            "实际执行模式由系统开关快照决定：本轮已启用 Harness V3。"
            "只能基于本轮持久化的假设、授权代码证据与 Critic 判定描述 V3 结果；"
            "没有对应记录时必须明确说明证据不足。"
        )
    return (
        "实际执行模式由系统开关快照决定：本轮未启用 Harness V3，"
        "当前结果仅来自受限旧工作流的确定性扫描与 LLM 分析。"
        "无论用户目标如何措辞，都不得声称完成 Harness V3、V3 验收或 V3 攻击路径验证；"
        "需要时应明确说明该能力未启用。"
    )


def guard_analysis_for_execution_mode(run: AgentRun, analysis: str) -> str:
    """移除旧工作流中不可信的 V3 验收声明，并添加可核验的模式说明。"""
    content = (analysis or "").strip()
    if not content or AgentFeatureFlags().for_run(run).harness_v3:
        return content
    if not _contains_non_v3_claim(content):
        return content

    filtered = _remove_non_v3_claims(content)
    disclosure = (
        "【执行模式说明】本轮未启用 Harness V3；以下仅为受限旧工作流的"
        "扫描与分析结果，不能作为 V3 攻击路径验证或 V3 验收结论。"
    )
    if not filtered:
        return disclosure
    return f"{disclosure}\n\n{filtered}"


def _contains_non_v3_claim(content: str) -> bool:
    return any(marker in content for marker in _NON_V3_CLAIM_MARKERS)


def _remove_non_v3_claims(content: str) -> str:
    kept = [
        sentence
        for sentence in _SENTENCE_BOUNDARY.split(content)
        if sentence and not any(marker in sentence for marker in _NON_V3_CLAIM_MARKERS)
    ]
    return "".join(kept).strip()
