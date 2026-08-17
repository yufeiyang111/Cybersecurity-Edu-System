# -*- coding: utf-8 -*-
"""Harness V3 已知漏洞/安全对照矩阵。"""
from __future__ import annotations

import pytest

from app.services.security_agent.harness_v3.evidence_critic import EvidenceCritic

from harness_v3_security_fixtures import KNOWN_SECURITY_CASES
from harness_v3_security_test_support import (
    build_evidence,
    persist_hypothesis,
    with_claimed_requirements,
)


@pytest.mark.parametrize("case", KNOWN_SECURITY_CASES, ids=lambda case: case.key)
def test_known_vulnerable_case_confirms_only_with_authorized_code_evidence(
    app,
    tmp_path,
    case,
):
    """每个漏洞夹具都必须命中固定技能，且确认结果携带受授权的源码位置。"""
    with app.app_context():
        hypothesis = persist_hypothesis(tmp_path, case, case.vulnerable_source)
        evidence = with_claimed_requirements(
            hypothesis,
            build_evidence(
                case,
                case.vulnerable_source,
                control_status="absent",
                include_guard=False,
            ),
        )

        decision = EvidenceCritic().evaluate(
            hypothesis,
            evidence,
            budget_exhausted=False,
        )

        assert decision.verdict == "confirm_candidate"
        assert decision.satisfied_evidence == tuple(hypothesis.required_evidence_json)
        assert all(
            location.file_path == hypothesis.authorized_scopes_json[0]["file_path"]
            and location.start_line >= hypothesis.authorized_scopes_json[0]["start_line"]
            and location.end_line <= hypothesis.authorized_scopes_json[0]["end_line"]
            for location in evidence.locations
        )


@pytest.mark.parametrize("case", KNOWN_SECURITY_CASES, ids=lambda case: case.key)
def test_safe_counterpart_rejects_candidate_when_authorized_control_exists(
    app,
    tmp_path,
    case,
):
    """安全对照有受授权控制证据时，不能被错误确认成漏洞。"""
    with app.app_context():
        hypothesis = persist_hypothesis(tmp_path, case, case.safe_source)
        evidence = with_claimed_requirements(
            hypothesis,
            build_evidence(
                case,
                case.safe_source,
                control_status="present",
                include_guard=True,
            ),
        )

        decision = EvidenceCritic().evaluate(
            hypothesis,
            evidence,
            budget_exhausted=False,
        )

        assert decision.verdict == "reject_hypothesis"
        assert decision.next_action == {"action": "reject_protected_path"}