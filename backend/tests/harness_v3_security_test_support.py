# -*- coding: utf-8 -*-
"""Harness V3 安全矩阵测试的固定组装辅助函数。"""
from __future__ import annotations

from app.services.security_agent.harness_v3.evidence_critic import (
    HypothesisEvidence,
    HypothesisEvidenceLocation,
)
from app.services.security_agent.harness_v3.hypothesis_planner import (
    FindingSignal,
    HypothesisPlanner,
)
from app.services.security_agent.harness_v3.hypothesis_service import (
    HypothesisPersistenceService,
)

from harness_v3_security_fixtures import marker_line
from test_agent_harness_v3_deep_review import _make_v3_run


def persist_hypothesis(tmp_path, case, source: str):
    """经由规则型 Planner 与持久化服务创建单条受限漏洞假设。"""
    run = _make_v3_run(tmp_path, files={case.file_path: source})
    signal_line = marker_line(source, "MATRIX_SINK")
    signal = FindingSignal(
        file_path=case.file_path,
        start_line=signal_line,
        end_line=signal_line,
        severity="high",
        rule_id=case.rule_id,
        category=case.category,
        cwe_id=case.cwe_id,
        message=case.message,
    )
    planner = HypothesisPlanner(
        provider_selector=lambda **_kwargs: None,
        finding_reader=lambda _run: (signal,),
    )
    batch = planner.build(run, evidence_summary=None)

    assert batch.planner_source == "rule_based_policy"
    assert batch.fallback_reason == "provider_unavailable"
    assert len(batch.drafts) == 1
    assert batch.drafts[0].skill_key == case.skill_key

    return HypothesisPersistenceService().persist(run, batch)[0]


def build_evidence(
    case,
    source: str,
    *,
    control_status: str,
    include_guard: bool,
) -> HypothesisEvidence:
    """从夹具标记组装不含源码文本的结构化 Observation 摘要。"""
    locations = [
        HypothesisEvidenceLocation(
            file_path=case.file_path,
            start_line=marker_line(source, "MATRIX_SOURCE"),
            end_line=marker_line(source, "MATRIX_SOURCE"),
            role="source",
        ),
        HypothesisEvidenceLocation(
            file_path=case.file_path,
            start_line=marker_line(source, "MATRIX_SINK"),
            end_line=marker_line(source, "MATRIX_SINK"),
            role=case.sink_role,
        ),
    ]
    if include_guard:
        locations.append(
            HypothesisEvidenceLocation(
                file_path=case.file_path,
                start_line=marker_line(source, "MATRIX_GUARD"),
                end_line=marker_line(source, "MATRIX_GUARD"),
                role="guard",
            )
        )
    return HypothesisEvidence(
        observation_id=1,
        locations=tuple(locations),
        claimed_satisfied=(),
        proof_gaps=(),
        control_assessments=((case.control_evidence_key, control_status),),
    )


def with_claimed_requirements(
    hypothesis,
    evidence: HypothesisEvidence,
    *,
    control_assessments: tuple[tuple[str, str], ...] | None = None,
) -> HypothesisEvidence:
    """为控制契约测试填入 Planner 固定的 required_evidence。"""
    return HypothesisEvidence(
        observation_id=evidence.observation_id,
        locations=evidence.locations,
        claimed_satisfied=tuple(hypothesis.required_evidence_json),
        proof_gaps=evidence.proof_gaps,
        control_assessments=(
            evidence.control_assessments
            if control_assessments is None
            else control_assessments
        ),
    )