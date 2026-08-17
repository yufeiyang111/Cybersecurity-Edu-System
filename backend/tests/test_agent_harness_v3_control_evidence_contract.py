# -*- coding: utf-8 -*-
"""Harness V3 控制类证据三态契约与边界回归。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.security_agent.harness_v3.evidence_critic import EvidenceCritic
from app.services.security_agent.observation_validator import ObservationValidationError
from app.services.security_agent.tools.review_tools import (
    _normalize_v3_control_assessments,
)

from harness_v3_security_fixtures import KNOWN_SECURITY_CASES
from harness_v3_security_test_support import (
    build_evidence,
    persist_hypothesis,
    with_claimed_requirements,
)


def test_control_present_without_authorized_guard_stays_unconfirmed(app, tmp_path):
    """Provider 单方面声称有防护、却不给授权 guard 位置时，不能直接关闭候选。"""
    case = KNOWN_SECURITY_CASES[0]
    with app.app_context():
        hypothesis = persist_hypothesis(tmp_path, case, case.safe_source)
        evidence = with_claimed_requirements(
            hypothesis,
            build_evidence(
                case,
                case.safe_source,
                control_status="present",
                include_guard=False,
            ),
        )

        decision = EvidenceCritic().evaluate(
            hypothesis,
            evidence,
            budget_exhausted=False,
        )

        assert decision.verdict == "request_evidence"
        assert "缺少受授权的控制措施代码位置" in decision.evidence_gaps


def test_control_absence_conflicting_with_guard_location_stays_unconfirmed(
    app,
    tmp_path,
):
    """“控制缺失”与 guard 位置矛盾时不能确认，避免模型用冲突证据抬高结论。"""
    case = KNOWN_SECURITY_CASES[0]
    with app.app_context():
        hypothesis = persist_hypothesis(tmp_path, case, case.safe_source)
        evidence = with_claimed_requirements(
            hypothesis,
            build_evidence(
                case,
                case.safe_source,
                control_status="absent",
                include_guard=True,
            ),
        )

        decision = EvidenceCritic().evaluate(
            hypothesis,
            evidence,
            budget_exhausted=False,
        )

        assert decision.verdict == "request_evidence"
        assert "控制状态与授权 guard 位置矛盾" in decision.evidence_gaps


@pytest.mark.parametrize(
    ("control_assessments", "expected_gap"),
    (
        ((), "未声明控制状态：parameterization_or_absence"),
        (
            (("parameterization_or_absence", "unknown"),),
            "控制状态未知：parameterization_or_absence",
        ),
    ),
    ids=("missing", "unknown"),
)
def test_missing_or_unknown_control_status_stays_unconfirmed(
    app,
    tmp_path,
    control_assessments,
    expected_gap,
):
    """控制状态缺失或未知时只能请求补证，不能据此确认漏洞候选。"""
    case = KNOWN_SECURITY_CASES[0]
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
            control_assessments=control_assessments,
        )

        decision = EvidenceCritic().evaluate(
            hypothesis,
            evidence,
            budget_exhausted=False,
        )

        assert decision.verdict == "request_evidence"
        assert expected_gap in decision.evidence_gaps


def test_provider_control_assessments_are_limited_to_current_hypothesis():
    """Provider 只能对本轮控制类证据条件给出固定三态，不能自造条件或状态。"""
    request = SimpleNamespace(
        required_evidence=(
            "untrusted_input",
            "query_or_command_sink",
            "parameterization_or_absence",
        )
    )
    parsed = {
        "detail": {
            "control_assessments": {
                "parameterization_or_absence": "absent",
            }
        }
    }

    _normalize_v3_control_assessments(parsed, request)

    assert parsed["detail"] == {
        "v3_control_assessments": {
            "parameterization_or_absence": "absent",
        }
    }

    with pytest.raises(ObservationValidationError, match="未授权控制证据条件"):
        _normalize_v3_control_assessments(
            {
                "detail": {
                    "control_assessments": {
                        "prompt_defined_control": "absent",
                    }
                }
            },
            request,
        )

    with pytest.raises(ObservationValidationError, match="控制状态"):
        _normalize_v3_control_assessments(
            {
                "detail": {
                    "control_assessments": {
                        "parameterization_or_absence": "bypass",
                    }
                }
            },
            request,
        )