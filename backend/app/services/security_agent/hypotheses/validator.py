# -*- coding: utf-8 -*-
"""Harness V3 漏洞假设校验：技能、证据、数量和授权位置必须同时成立。"""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.services.security_agent.audit_skills import AuditSkillCatalog
from app.services.security_agent.hypotheses.contracts import (
    AuditHypothesisDraft,
    CodeLocationScope,
)


class HypothesisValidationError(ValueError):
    """候选漏洞假设违反冻结安全契约。"""


class HypothesisValidator:
    """将模型或规则规划输出收敛为可验证、可授权的少量假设。"""

    _KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
    _ALLOWED_PLANNER_SOURCES = frozenset({"llm_live", "rule_based_policy"})
    _MAX_TITLE_CHARS = 200
    _MAX_TARGET_SUMMARY_CHARS = 1000
    _MAX_SCOPE_LINES = 1000

    def __init__(
        self,
        catalog: AuditSkillCatalog | None = None,
        *,
        max_hypotheses: int = 3,
    ) -> None:
        if not isinstance(max_hypotheses, int) or isinstance(max_hypotheses, bool):
            raise ValueError("max_hypotheses 必须是正整数")
        if not 1 <= max_hypotheses <= 10:
            raise ValueError("max_hypotheses 必须在 1 至 10 之间")
        self._catalog = catalog or AuditSkillCatalog()
        self._max_hypotheses = max_hypotheses

    def validate_batch(
        self,
        drafts: tuple[AuditHypothesisDraft, ...],
        *,
        allowed_scopes: tuple[CodeLocationScope, ...],
    ) -> tuple[AuditHypothesisDraft, ...]:
        if not isinstance(drafts, tuple):
            raise HypothesisValidationError("漏洞假设批次必须是元组")
        if len(drafts) > self._max_hypotheses:
            raise HypothesisValidationError(
                f"一次最多允许 {self._max_hypotheses} 条漏洞假设"
            )
        validated_allowed_scopes = self._validate_allowed_scopes(allowed_scopes)
        keys: set[str] = set()
        for draft in drafts:
            self._validate_draft(draft, validated_allowed_scopes)
            if draft.hypothesis_key in keys:
                raise HypothesisValidationError("同一批次不允许重复 hypothesis_key")
            keys.add(draft.hypothesis_key)
        return drafts

    def _validate_draft(
        self,
        draft: AuditHypothesisDraft,
        allowed_scopes: tuple[CodeLocationScope, ...],
    ) -> None:
        if not isinstance(draft, AuditHypothesisDraft):
            raise HypothesisValidationError("漏洞假设必须符合冻结数据契约")
        if not self._KEY_PATTERN.fullmatch(draft.hypothesis_key or ""):
            raise HypothesisValidationError("hypothesis_key 格式非法")
        skill = self._catalog.get(draft.skill_key)
        if skill is None:
            raise HypothesisValidationError("未注册审计技能，拒绝动态 Prompt Skill")
        self._validate_text(draft.title, "title", self._MAX_TITLE_CHARS)
        self._validate_text(
            draft.target_summary,
            "target_summary",
            self._MAX_TARGET_SUMMARY_CHARS,
        )
        if not isinstance(draft.priority, int) or isinstance(draft.priority, bool):
            raise HypothesisValidationError("priority 必须是整数")
        if not 1 <= draft.priority <= 100:
            raise HypothesisValidationError("priority 必须在 1 至 100 之间")
        if draft.planner_source not in self._ALLOWED_PLANNER_SOURCES:
            raise HypothesisValidationError("planner_source 不受支持")
        self._validate_required_evidence(draft, skill.required_evidence)
        self._validate_authorized_scopes(draft.authorized_scopes, allowed_scopes)

    @staticmethod
    def _validate_text(value: str, field: str, maximum: int) -> None:
        if not isinstance(value, str) or not value.strip():
            raise HypothesisValidationError(f"{field} 不能为空")
        if len(value.strip()) > maximum:
            raise HypothesisValidationError(f"{field} 超过最大长度")

    def _validate_required_evidence(
        self,
        draft: AuditHypothesisDraft,
        required_by_skill: tuple[str, ...],
    ) -> None:
        evidence = draft.required_evidence
        if not isinstance(evidence, tuple) or not evidence:
            raise HypothesisValidationError("漏洞假设缺少 required_evidence")
        normalized = tuple(str(item or "").strip() for item in evidence)
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise HypothesisValidationError("required_evidence 必须是非重复非空字符串")
        missing = [item for item in required_by_skill if item not in normalized]
        if missing:
            raise HypothesisValidationError(
                f"漏洞假设缺少技能所需证据：{', '.join(missing)}"
            )

    def _validate_allowed_scopes(
        self,
        allowed_scopes: tuple[CodeLocationScope, ...],
    ) -> tuple[CodeLocationScope, ...]:
        if not isinstance(allowed_scopes, tuple) or not allowed_scopes:
            raise HypothesisValidationError("必须提供授权代码范围")
        for scope in allowed_scopes:
            self._validate_scope_shape(scope)
        return allowed_scopes

    def _validate_authorized_scopes(
        self,
        scopes: tuple[CodeLocationScope, ...],
        allowed_scopes: tuple[CodeLocationScope, ...],
    ) -> None:
        if not isinstance(scopes, tuple) or not scopes:
            raise HypothesisValidationError("漏洞假设缺少授权代码范围")
        for scope in scopes:
            self._validate_scope_shape(scope)
            if not any(self._is_within(scope, allowed) for allowed in allowed_scopes):
                raise HypothesisValidationError("代码位置不在授权范围内")

    def _validate_scope_shape(self, scope: CodeLocationScope) -> None:
        if not isinstance(scope, CodeLocationScope):
            raise HypothesisValidationError("授权代码范围必须是位置契约")
        file_path = scope.file_path
        if not isinstance(file_path, str) or not file_path.strip():
            raise HypothesisValidationError("代码路径不能为空")
        normalized_path = file_path.strip()
        path = PurePosixPath(normalized_path)
        if (
            "\\" in normalized_path
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise HypothesisValidationError("代码路径必须是项目内相对路径")
        if not isinstance(scope.start_line, int) or isinstance(scope.start_line, bool):
            raise HypothesisValidationError("代码范围起始行非法")
        if not isinstance(scope.end_line, int) or isinstance(scope.end_line, bool):
            raise HypothesisValidationError("代码范围结束行非法")
        if scope.start_line < 1 or scope.end_line < scope.start_line:
            raise HypothesisValidationError("代码范围行号非法")
        if scope.end_line - scope.start_line + 1 > self._MAX_SCOPE_LINES:
            raise HypothesisValidationError("代码范围超过单次授权上限")

    @staticmethod
    def _is_within(candidate: CodeLocationScope, allowed: CodeLocationScope) -> bool:
        return (
            candidate.file_path == allowed.file_path
            and candidate.start_line >= allowed.start_line
            and candidate.end_line <= allowed.end_line
        )