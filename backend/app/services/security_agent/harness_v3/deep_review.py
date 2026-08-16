# -*- coding: utf-8 -*-
"""Harness V3 的目标化 Deep Review 输入与受限 Context Pack。

V3 不接受模型自由扩展的 focus、file_hints 或源码范围。工具输入只引用已持久化并
经过 HypothesisValidator 的假设；源码行仅存在于本次内存中的 DeepReviewContext，绝不
写入假设或判定表。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from flask import current_app, has_app_context

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis, AuditHypothesisStatus
from app.models.agent_runtime import AgentRun
from app.models.security import ProjectSnapshot
from app.services.project_security_graph.code_slice import (
    CodeSliceError,
    CodeSliceForbidden,
    read_code_slice,
)
from app.services.security_agent.audit_skills import AuditSkillCatalog
from app.services.security_agent.context_builder import (
    DEFAULT_MAX_CITATIONS,
    DEFAULT_MAX_FILES,
    CitationCandidate,
    CodeSliceEvidence,
    ContextBuilder,
    DeepReviewContext,
)
from app.services.security_agent.harness_v3.budget import resolve_v3_context_char_budget
from app.services.security_agent.hypotheses.contracts import (
    AuditHypothesisDraft,
    CodeLocationScope,
)
from app.services.security_agent.hypotheses.validator import (
    HypothesisValidationError,
    HypothesisValidator,
)

_MAX_SCOPE_FILES = 20
_MAX_SCOPE_SLICE_LINES = 200
_V3_INPUT_KEYS = frozenset(
    {
        "hypothesis_id",
        "skill_key",
        "required_evidence",
        "context_budget_chars",
        "review_kind",
    }
)
_LEGACY_FREE_INPUT_KEYS = frozenset({"focus", "file_hints", "entrypoints"})
_ALLOWED_REVIEW_KINDS = frozenset({"primary", "supplemental"})


class V3DeepReviewInputError(ValueError):
    """V3 Deep Review 输入未绑定到当前 Run 的已授权假设。"""


class TargetedContextBuildError(ValueError):
    """无法仅基于授权范围构建最小充分代码证据。"""


@dataclass(frozen=True)
class V3DeepReviewRequest:
    """已验证的 V3 Deep Review 请求，不包含任何源码行。"""

    hypothesis_id: int
    hypothesis: AgentAuditHypothesis
    skill_key: str
    required_evidence: tuple[str, ...]
    authorized_scopes: tuple[CodeLocationScope, ...]
    focus: str
    review_kind: str
    explicit_context_chars: int | None


class V3DeepReviewInputResolver:
    """把内部工具输入收敛为已持久化假设的只读引用。"""

    def __init__(self, catalog: AuditSkillCatalog | None = None) -> None:
        self._catalog = catalog or AuditSkillCatalog()
        self._validator = HypothesisValidator(self._catalog)

    def resolve(
        self,
        run: AgentRun,
        raw_input: dict | None,
    ) -> V3DeepReviewRequest:
        if not isinstance(raw_input, dict):
            raise V3DeepReviewInputError("V3 Deep Review 输入必须是对象")
        unknown = set(raw_input) - _V3_INPUT_KEYS - _LEGACY_FREE_INPUT_KEYS
        if unknown:
            raise V3DeepReviewInputError("V3 Deep Review 包含未授权输入字段")
        legacy_keys = [key for key in _LEGACY_FREE_INPUT_KEYS if raw_input.get(key)]
        if legacy_keys:
            raise V3DeepReviewInputError("V3 Deep Review 不接受自由文本或自由文件范围")

        hypothesis_id = _positive_int(raw_input.get("hypothesis_id"), "hypothesis_id")
        hypothesis = db.session.get(AgentAuditHypothesis, hypothesis_id)
        if hypothesis is None or hypothesis.run_id != run.id:
            raise V3DeepReviewInputError("漏洞假设不属于当前任务")
        if _status_value(hypothesis.status) in {
            AuditHypothesisStatus.CONFIRMED.value,
            AuditHypothesisStatus.REJECTED.value,
            AuditHypothesisStatus.STOPPED_FOR_BUDGET.value,
        }:
            raise V3DeepReviewInputError("漏洞假设已经结束，不能再次执行 Deep Review")

        skill_key = str(raw_input.get("skill_key") or "").strip()
        if not skill_key or skill_key != hypothesis.skill_key:
            raise V3DeepReviewInputError("审计技能与已授权漏洞假设不匹配")
        if self._catalog.get(skill_key) is None:
            raise V3DeepReviewInputError("审计技能未注册")

        required_evidence = _string_tuple(raw_input.get("required_evidence"))
        persisted_evidence = _string_tuple(hypothesis.required_evidence_json)
        if not required_evidence or required_evidence != persisted_evidence:
            raise V3DeepReviewInputError("证据条件与已授权漏洞假设不匹配")

        scopes = _scopes_from_hypothesis(hypothesis)
        try:
            draft = AuditHypothesisDraft(
                hypothesis_key=hypothesis.hypothesis_key,
                skill_key=skill_key,
                title=hypothesis.title,
                target_summary=hypothesis.target_summary,
                priority=int(hypothesis.priority),
                required_evidence=persisted_evidence,
                authorized_scopes=scopes,
                planner_source=str(hypothesis.planner_source),
            )
            self._validator.validate_batch((draft,), allowed_scopes=scopes)
        except (HypothesisValidationError, TypeError, ValueError) as exc:
            raise V3DeepReviewInputError("漏洞假设的授权范围无效") from exc

        review_kind = str(raw_input.get("review_kind") or "primary").strip()
        if review_kind not in _ALLOWED_REVIEW_KINDS:
            raise V3DeepReviewInputError("review_kind 不受支持")
        explicit_context_chars = _optional_context_budget(
            raw_input.get("context_budget_chars")
        )
        return V3DeepReviewRequest(
            hypothesis_id=hypothesis.id,
            hypothesis=hypothesis,
            skill_key=skill_key,
            required_evidence=required_evidence,
            authorized_scopes=scopes,
            focus=hypothesis.target_summary,
            review_kind=review_kind,
            explicit_context_chars=explicit_context_chars,
        )


class TargetedDeepReviewContextBuilder:
    """只读取假设授权范围内源码的 Context Pack 构造器。"""

    def __init__(
        self,
        *,
        citation_collector: Callable[
            [str, int], tuple[tuple[CitationCandidate, ...], tuple[str, ...]]
        ]
        | None = None,
    ) -> None:
        self._citation_collector = citation_collector or ContextBuilder()._collect_citations

    def build(
        self,
        run: AgentRun,
        request: V3DeepReviewRequest,
        *,
        max_context_chars: int | None = None,
    ) -> DeepReviewContext:
        if request.hypothesis.run_id != run.id:
            raise TargetedContextBuildError("漏洞假设与任务不匹配")
        snapshot = db.session.get(ProjectSnapshot, run.snapshot_id)
        if snapshot is None:
            raise TargetedContextBuildError("快照不存在，无法构建授权代码证据")

        char_budget = resolve_v3_context_char_budget(
            explicit_chars=(
                max_context_chars
                if max_context_chars is not None
                else request.explicit_context_chars
            ),
            config=current_app.config if has_app_context() else None,
        )
        configured_limit = getattr(run, "max_deep_review_files", None)
        file_limit = min(
            _MAX_SCOPE_FILES,
            configured_limit if isinstance(configured_limit, int) and configured_limit > 0 else DEFAULT_MAX_FILES,
        )
        evidence = self._read_authorized_scopes(
            snapshot,
            request.authorized_scopes,
            file_limit=file_limit,
            char_budget=char_budget,
        )
        if not evidence:
            raise TargetedContextBuildError(
                "没有可读取的授权代码证据，拒绝回退到无关文件范围"
            )

        citations, injected_doc_ids = self._citation_collector(
            request.focus,
            DEFAULT_MAX_CITATIONS,
        )
        total_chars = sum(len("\n".join(item.lines)) for item in evidence)
        return DeepReviewContext(
            focus=request.focus,
            entrypoints=tuple(dict.fromkeys(scope.file_path for scope in request.authorized_scopes)),
            files=tuple(evidence),
            citations=tuple(citations),
            injected_doc_ids=tuple(injected_doc_ids),
            total_chars=total_chars,
        )

    @staticmethod
    def _read_authorized_scopes(
        snapshot: ProjectSnapshot,
        scopes: tuple[CodeLocationScope, ...],
        *,
        file_limit: int,
        char_budget: int,
    ) -> list[CodeSliceEvidence]:
        evidence: list[CodeSliceEvidence] = []
        used_chars = 0
        seen_ranges: set[tuple[str, int, int]] = set()
        for scope in scopes:
            if len(evidence) >= file_limit or used_chars >= char_budget:
                break
            end_line = min(scope.end_line, scope.start_line + _MAX_SCOPE_SLICE_LINES - 1)
            range_key = (scope.file_path, scope.start_line, end_line)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)
            try:
                payload = read_code_slice(
                    snapshot,
                    scope.file_path,
                    scope.start_line,
                    end_line,
                    "harness_v3_authorized_hypothesis",
                )
            except (CodeSliceError, CodeSliceForbidden):
                continue
            lines = _fit_lines(tuple(payload.get("lines") or ()), char_budget - used_chars)
            if not lines:
                continue
            actual_end = scope.start_line + len(lines) - 1
            evidence.append(
                CodeSliceEvidence(
                    file_path=scope.file_path,
                    start_line=scope.start_line,
                    end_line=actual_end,
                    lines=lines,
                )
            )
            used_chars += len("\n".join(lines))
        return evidence


def _scopes_from_hypothesis(
    hypothesis: AgentAuditHypothesis,
) -> tuple[CodeLocationScope, ...]:
    raw_scopes = hypothesis.authorized_scopes_json
    if not isinstance(raw_scopes, list) or not raw_scopes:
        raise V3DeepReviewInputError("漏洞假设没有授权范围")
    scopes: list[CodeLocationScope] = []
    for raw in raw_scopes:
        if not isinstance(raw, dict):
            raise V3DeepReviewInputError("漏洞假设授权范围格式非法")
        try:
            scope = CodeLocationScope(
                file_path=str(raw["file_path"]),
                start_line=int(raw["start_line"]),
                end_line=int(raw["end_line"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise V3DeepReviewInputError("漏洞假设授权范围格式非法") from exc
        scopes.append(scope)
    return tuple(scopes)


def _string_tuple(value) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _positive_int(value, field: str) -> int:
    if isinstance(value, bool):
        raise V3DeepReviewInputError(f"{field} 必须是正整数")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise V3DeepReviewInputError(f"{field} 必须是正整数") from exc
    if parsed <= 0:
        raise V3DeepReviewInputError(f"{field} 必须是正整数")
    return parsed


def _optional_context_budget(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise V3DeepReviewInputError("context_budget_chars 必须是整数")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise V3DeepReviewInputError("context_budget_chars 必须是整数") from exc
    try:
        return resolve_v3_context_char_budget(explicit_chars=parsed)
    except ValueError as exc:
        raise V3DeepReviewInputError(str(exc)) from exc


def _fit_lines(lines: tuple[str, ...], remaining_chars: int) -> tuple[str, ...]:
    selected: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + (1 if selected else 0)
        if used + cost > remaining_chars:
            break
        selected.append(line)
        used += cost
    return tuple(selected)


def _status_value(value: object) -> str:
    return value.value if isinstance(value, Enum) else str(value)
