# -*- coding: utf-8 -*-
"""漏洞假设的无源码数据契约。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodeLocationScope:
    """仅保存授权位置，不携带 CodeSliceEvidence 的源码行。"""

    file_path: str
    start_line: int
    end_line: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass(frozen=True)
class AuditHypothesisDraft:
    """规划器输出的候选漏洞假设，提交持久化前必须经过 HypothesisValidator。"""

    hypothesis_key: str
    skill_key: str
    title: str
    target_summary: str
    priority: int
    required_evidence: tuple[str, ...]
    authorized_scopes: tuple[CodeLocationScope, ...]
    planner_source: str