# -*- coding: utf-8 -*-
"""CompletionCriteria（T06，spec §6.3/§11.2）：每种模式的强制节点与完成条件。

- 强制基线（inventory + baseline_scan）对所有模式不可绕过；
- baseline 是显式"策略工作流"：模型仅生成安全最终摘要；
- hybrid / deep_audit 追加覆盖、风险与报告条件。
"""
from __future__ import annotations

from dataclasses import dataclass

MANDATORY_BASELINE_KEYS = frozenset({"inventory", "baseline_scan"})

_MODE_MANDATORY_NODES = {
    "baseline": ("inventory", "baseline_scan"),
    "hybrid": (
        "inventory",
        "baseline_scan",
        "coverage_analysis",
        "risk_ranking",
    ),
    "deep_audit": (
        "inventory",
        "baseline_scan",
        "coverage_analysis",
        "risk_ranking",
        "deep_review",
        "report",
    ),
}


@dataclass(frozen=True)
class CompletionCriteria:
    mode: str
    mandatory_node_keys: tuple[str, ...]
    coverage_required: bool = False
    evidence_required: bool = False

    @classmethod
    def for_mode(cls, mode: str) -> "CompletionCriteria":
        mandatory = _MODE_MANDATORY_NODES.get(
            mode, _MODE_MANDATORY_NODES["baseline"]
        )
        return cls(
            mode=mode,
            mandatory_node_keys=tuple(mandatory),
            coverage_required=mode in {"hybrid", "deep_audit"},
            evidence_required=mode == "deep_audit",
        )
