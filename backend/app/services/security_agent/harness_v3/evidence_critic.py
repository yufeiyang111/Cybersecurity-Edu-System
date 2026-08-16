# -*- coding: utf-8 -*-
"""Harness V3 的独立证据批判器：没有受授权代码证据就不能确认候选。"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.agent_hypothesis import AgentAuditHypothesis
from app.services.security_agent.audit_skills import AuditSkillCatalog
from app.services.security_agent.hypotheses.contracts import CodeLocationScope

CRITIC_VERSION = "evidence_critic_v1"

_EVIDENCE_ROLE_REQUIREMENTS: dict[str, frozenset[str]] = {
    "subject": frozenset({"source", "entry"}),
    "object": frozenset({"sink", "object"}),
    "authorization_guard": frozenset({"guard"}),
    "untrusted_input": frozenset({"source", "entry"}),
    "query_or_command_sink": frozenset({"sink"}),
    "parameterization_or_absence": frozenset({"guard"}),
    "dangerous_sink": frozenset({"sink"}),
    "guard_or_absence": frozenset({"guard"}),
    "untrusted_path_or_url": frozenset({"source", "entry"}),
    "file_or_network_sink": frozenset({"sink"}),
    "allowlist_or_absence": frozenset({"guard"}),
    "unsafe_runtime_setting": frozenset({"configuration"}),
    "production_guard_or_absence": frozenset({"configuration", "guard"}),
}


@dataclass(frozen=True)
class HypothesisEvidenceLocation:
    """Observation 中的代码位置元数据，不包含源码行。"""

    file_path: str
    start_line: int
    end_line: int
    role: str


@dataclass(frozen=True)
class HypothesisEvidence:
    """交给 Critic 的受限 Observation 摘要。"""

    observation_id: int | None
    locations: tuple[HypothesisEvidenceLocation, ...]
    claimed_satisfied: tuple[str, ...]
    proof_gaps: tuple[str, ...]


@dataclass(frozen=True)
class CriticDecision:
    """Critic 输出必须可以安全持久化，且不携带 Provider 原文或源码。"""

    verdict: str
    reason_summary: str
    evidence_gaps: tuple[str, ...]
    satisfied_evidence: tuple[str, ...]
    next_action: dict[str, object]
    critic_version: str = CRITIC_VERSION


class EvidenceCritic:
    """独立核验技能条件、观察位置和授权范围，避免 Planner 自证。"""

    def __init__(self, catalog: AuditSkillCatalog | None = None) -> None:
        self._catalog = catalog or AuditSkillCatalog()

    def evaluate(
        self,
        hypothesis: AgentAuditHypothesis,
        evidence: HypothesisEvidence,
        *,
        budget_exhausted: bool,
    ) -> CriticDecision:
        """只依据结构化证据判断，不信任模型的文字结论。"""
        if budget_exhausted:
            return CriticDecision(
                verdict="stop_for_budget",
                reason_summary="预算已耗尽，停止继续扩展该漏洞假设。",
                evidence_gaps=("未在预算内完成所需代码证据核验",),
                satisfied_evidence=(),
                next_action={"action": "stop_for_budget"},
            )

        required = tuple(
            str(item).strip()
            for item in (hypothesis.required_evidence_json or [])
            if str(item).strip()
        )
        if not required:
            return CriticDecision(
                verdict="reject_hypothesis",
                reason_summary="漏洞假设缺少受版本控制的证据条件，不能继续确认。",
                evidence_gaps=("缺少 required_evidence",),
                satisfied_evidence=(),
                next_action={"action": "reject_invalid_hypothesis"},
            )

        authorized = _authorized_scopes(hypothesis)
        valid_locations = tuple(
            location
            for location in evidence.locations
            if _location_is_authorized(location, authorized)
        )
        if not valid_locations:
            return CriticDecision(
                verdict="needs_more_evidence",
                reason_summary="未获得落在授权范围内的代码位置，不能确认漏洞候选。",
                evidence_gaps=("缺少受授权的代码位置证据",),
                satisfied_evidence=(),
                next_action={"action": "close_as_needs_evidence"},
            )

        claims = tuple(
            item
            for item in dict.fromkeys(str(value).strip() for value in evidence.claimed_satisfied)
            if item in required
        )
        roles = {str(location.role or "").strip().lower() for location in valid_locations}
        satisfied: list[str] = []
        gaps: list[str] = []
        for evidence_key in required:
            expected_roles = _EVIDENCE_ROLE_REQUIREMENTS.get(evidence_key, frozenset())
            if evidence_key not in claims:
                gaps.append(f"未声明已满足证据条件：{evidence_key}")
                continue
            if expected_roles and not roles.intersection(expected_roles):
                gaps.append(f"{evidence_key} 缺少与条件匹配的代码位置")
                continue
            satisfied.append(evidence_key)

        if evidence.proof_gaps:
            gaps.append("Observation 仍存在证据缺口")

        if not gaps and len(satisfied) == len(required):
            return CriticDecision(
                verdict="confirm_candidate",
                reason_summary="已获得所需证据条件及其授权代码位置，作为候选漏洞进入人工复核。",
                evidence_gaps=(),
                satisfied_evidence=tuple(satisfied),
                next_action={"action": "complete_hypothesis"},
            )

        skill = self._catalog.get(hypothesis.skill_key)
        attempts = int(hypothesis.execution_attempt_count or 0)
        if skill is not None and attempts < skill.max_attempts:
            return CriticDecision(
                verdict="request_evidence",
                reason_summary="当前证据不足，允许在已授权范围内进行一次补充审查。",
                evidence_gaps=tuple(dict.fromkeys(gaps)),
                satisfied_evidence=tuple(satisfied),
                next_action={"action": "request_supplemental_review"},
            )
        return CriticDecision(
            verdict="needs_more_evidence",
            reason_summary="已达到该技能的受限审查次数，证据仍不足以确认候选漏洞。",
            evidence_gaps=tuple(dict.fromkeys(gaps)),
            satisfied_evidence=tuple(satisfied),
            next_action={"action": "close_as_needs_evidence"},
        )


def _authorized_scopes(hypothesis: AgentAuditHypothesis) -> tuple[CodeLocationScope, ...]:
    scopes: list[CodeLocationScope] = []
    for raw_scope in hypothesis.authorized_scopes_json or []:
        if not isinstance(raw_scope, dict):
            continue
        try:
            scope = CodeLocationScope(
                file_path=str(raw_scope.get("file_path") or "").strip(),
                start_line=int(raw_scope.get("start_line")),
                end_line=int(raw_scope.get("end_line")),
            )
        except (TypeError, ValueError):
            continue
        if scope.file_path and scope.start_line > 0 and scope.end_line >= scope.start_line:
            scopes.append(scope)
    return tuple(scopes)


def _location_is_authorized(
    location: HypothesisEvidenceLocation,
    scopes: tuple[CodeLocationScope, ...],
) -> bool:
    if not location.file_path or location.start_line < 1 or location.end_line < location.start_line:
        return False
    return any(
        location.file_path == scope.file_path
        and location.start_line >= scope.start_line
        and location.end_line <= scope.end_line
        for scope in scopes
    )
