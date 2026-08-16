# -*- coding: utf-8 -*-
"""Harness V3 的确定性扫描线索与授权范围构造。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.models.agent_runtime import AgentRun
from app.models.security import ScanTask, SecurityFinding
from app.services.security_agent.audit_skills import AuditSkill
from app.services.security_agent.hypotheses.contracts import (
    AuditHypothesisDraft,
    CodeLocationScope,
)

MAX_FINDING_SIGNALS = 40
MAX_SCOPES_PER_HYPOTHESIS = 2
SCOPE_BEFORE_LINES = 20
SCOPE_AFTER_LINES = 40
MAX_SCOPE_LINES = 200


@dataclass(frozen=True)
class FindingSignal:
    """仅保存扫描 Finding 元数据，绝不包含源码行。"""

    file_path: str
    start_line: int | None
    end_line: int | None
    severity: str
    rule_id: str
    category: str
    cwe_id: str
    message: str

    def searchable_text(self) -> str:
        """只为冻结技能匹配构造文本，不将该文本持久化为假设。"""
        return " ".join(
            (
                self.file_path,
                self.severity,
                self.rule_id,
                self.category,
                self.cwe_id,
                self.message,
            )
        ).lower()


def read_finding_signals(run: AgentRun) -> tuple[FindingSignal, ...]:
    """读取最新扫描任务的元数据，完全不读取快照源码。"""
    if run.snapshot_id is None:
        return ()
    task = (
        ScanTask.query.filter_by(snapshot_id=run.snapshot_id)
        .order_by(ScanTask.id.desc())
        .first()
    )
    if task is None:
        return ()
    rows = (
        SecurityFinding.query.filter_by(task_id=task.id)
        .order_by(SecurityFinding.id.asc())
        .limit(MAX_FINDING_SIGNALS)
        .all()
    )
    return tuple(
        FindingSignal(
            file_path=str(row.file_path or ""),
            start_line=_positive_line(row.start_line),
            end_line=_positive_line(row.end_line),
            severity=_enum_value(row.severity),
            rule_id=str(row.rule_id or ""),
            category=str(row.category or ""),
            cwe_id=str(row.cwe_id or ""),
            message=str(row.message or "")[:500],
        )
        for row in rows
    )


def scopes_for_skill(
    skill: AuditSkill,
    signals: tuple[FindingSignal, ...],
) -> tuple[CodeLocationScope, ...]:
    """按冻结技能触发词选择最多两个确定性授权位置。"""
    matched = [
        signal
        for signal in signals
        if any(trigger in signal.searchable_text() for trigger in skill.trigger_signals)
    ]
    matched.sort(
        key=lambda signal: (
            -_severity_priority(signal.severity),
            signal.file_path,
            signal.start_line or 0,
        )
    )
    scopes: list[CodeLocationScope] = []
    for signal in matched:
        scope = _scope_for_signal(signal)
        if scope is not None and scope not in scopes:
            scopes.append(scope)
        if len(scopes) >= MAX_SCOPES_PER_HYPOTHESIS:
            break
    return tuple(scopes)


def scopes_from_indices(
    raw_indices: object,
    signals: tuple[FindingSignal, ...],
) -> tuple[CodeLocationScope, ...]:
    """把 Provider 选择的 signal 索引限制为本次确定性扫描范围。"""
    if not isinstance(raw_indices, list) or not raw_indices:
        raise ValueError("scope_indices 必须是非空数组")
    scopes: list[CodeLocationScope] = []
    for raw_index in raw_indices:
        if not isinstance(raw_index, int) or isinstance(raw_index, bool):
            raise ValueError("scope_indices 必须是整数数组")
        if raw_index < 0 or raw_index >= len(signals):
            raise ValueError("scope_indices 超出扫描位置范围")
        scope = _scope_for_signal(signals[raw_index])
        if scope is None:
            raise ValueError("扫描位置无法构造授权代码范围")
        if scope not in scopes:
            scopes.append(scope)
        if len(scopes) >= MAX_SCOPES_PER_HYPOTHESIS:
            break
    if not scopes:
        raise ValueError("scope_indices 未产生授权代码范围")
    return tuple(scopes)


def make_hypothesis_draft(
    *,
    run: AgentRun,
    skill: AuditSkill,
    scopes: tuple[CodeLocationScope, ...],
    priority: int,
    planner_source: str,
) -> AuditHypothesisDraft:
    """从冻结技能和授权范围构造不含源码的持久化草稿。"""
    first_scope = scopes[0]
    digest_input = "|".join(
        [str(run.id), skill.key]
        + [
            f"{scope.file_path}:{scope.start_line}:{scope.end_line}"
            for scope in scopes
        ]
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:20]
    return AuditHypothesisDraft(
        hypothesis_key=f"{skill.key[:36]}-{digest}",
        skill_key=skill.key,
        title=f"{skill.title}候选",
        target_summary=(
            f"核验 {first_scope.file_path} 第 {first_scope.start_line}-"
            f"{first_scope.end_line} 行附近的确定性扫描位置是否满足“{skill.title}”的最小证据条件。"
        ),
        priority=priority,
        required_evidence=skill.required_evidence,
        authorized_scopes=scopes,
        planner_source=planner_source,
    )


def max_hypotheses() -> int:
    """读取受上限约束的候选数，避免配置扩大审计面。"""
    try:
        from flask import current_app

        value = current_app.config.get("AGENT_HARNESS_V3_MAX_HYPOTHESES", 3)
    except RuntimeError:
        value = 3
    try:
        return min(3, max(1, int(value)))
    except (TypeError, ValueError):
        return 3


def normalize_priority(value: object) -> int:
    """将 Provider 优先级限制在产品允许的整数范围。"""
    if isinstance(value, int) and not isinstance(value, bool):
        return min(100, max(1, value))
    return 80


def run_mode(run: AgentRun) -> str:
    """兼容枚举和历史字符串模式。"""
    return str(
        getattr(
            getattr(run, "mode", None),
            "value",
            getattr(run, "mode", ""),
        )
        or ""
    )


def _scope_for_signal(signal: FindingSignal) -> CodeLocationScope | None:
    path = str(signal.file_path or "").strip()
    start = _positive_line(signal.start_line)
    end = _positive_line(signal.end_line) or start
    if not path or start is None or end is None:
        return None
    window_start = max(1, start - SCOPE_BEFORE_LINES)
    window_end = min(
        max(window_start, end + SCOPE_AFTER_LINES),
        window_start + MAX_SCOPE_LINES - 1,
    )
    return CodeLocationScope(path, window_start, window_end)


def _positive_line(value: object) -> int | None:
    try:
        line = int(value)
    except (TypeError, ValueError):
        return None
    return line if line > 0 else None


def _severity_priority(value: str) -> int:
    return {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }.get(str(value or "").lower(), 0)


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value) or "")
