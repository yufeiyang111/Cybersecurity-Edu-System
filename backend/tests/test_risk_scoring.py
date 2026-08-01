from __future__ import annotations

from dataclasses import dataclass

from app.services.risk_scoring import (
    FindingRiskContext,
    RiskPolicy,
    RiskScore,
    score_finding,
)


@dataclass
class _Finding:
    rule_id: str = "PY-SHELL-TRUE"
    category: str = "sast"
    severity: str = "high"
    confidence: float = 0.9
    cwe_id: str | None = "CWE-78"
    cve_id: str | None = None
    created_at: object | None = None


def test_risk_score_is_bounded_explainable_and_serializable():
    result = score_finding(_Finding())

    assert isinstance(result, RiskScore)
    assert 0 <= result.score <= 100
    assert result.priority in {"critical", "high", "medium", "low"}
    assert result.policy_version == "risk-v1"
    assert len(result.factors) == 10
    assert all(factor.contribution >= 0 for factor in result.factors)
    assert result.to_dict()["factors"]
    assert result.explanation


def test_critical_internet_exposed_finding_gets_critical_priority():
    context = FindingRiskContext(
        exploitability=1.0,
        internet_exposure=1.0,
        asset_criticality=1.0,
        data_sensitivity=1.0,
        dependency_reachability=1.0,
        exploit_maturity=1.0,
        fix_availability=1.0,
        age_days=365,
    )

    result = score_finding(
        _Finding(category="secret", severity="critical", confidence=1.0),
        context=context,
    )

    assert result.score >= 80
    assert result.priority == "critical"
    assert any(factor.name == "internet_exposure" and factor.value == 1.0 for factor in result.factors)


def test_policy_weights_can_be_overridden_without_changing_score_contract():
    policy = RiskPolicy.from_mapping(
        {
            "version": "enterprise-v2",
            "weights": {"severity": 1.0},
            "thresholds": {"critical": 90, "high": 70, "medium": 40},
        }
    )

    result = score_finding(_Finding(severity="critical"), policy=policy)

    assert result.policy_version == "enterprise-v2"
    assert result.score == 100
    assert result.priority == "critical"


def test_invalid_context_values_are_clamped_and_missing_values_are_safe():
    result = score_finding(
        _Finding(severity="unknown", confidence=3.0),
        context=FindingRiskContext(
            exploitability=-5,
            internet_exposure=8,
            age_days=-10,
        ),
    )

    assert 0 <= result.score <= 100
    assert all(0 <= factor.value <= 1 for factor in result.factors)
