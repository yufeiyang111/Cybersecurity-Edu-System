"""可解释的 Finding 风险评分与修复优先级服务。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

FACTOR_NAMES = (
    "severity",
    "confidence",
    "exploitability",
    "internet_exposure",
    "asset_criticality",
    "data_sensitivity",
    "dependency_reachability",
    "exploit_maturity",
    "fix_availability",
    "age",
)
DEFAULT_WEIGHTS = {
    "severity": 0.25,
    "confidence": 0.15,
    "exploitability": 0.12,
    "internet_exposure": 0.10,
    "asset_criticality": 0.10,
    "data_sensitivity": 0.08,
    "dependency_reachability": 0.07,
    "exploit_maturity": 0.05,
    "fix_availability": 0.05,
    "age": 0.03,
}
DEFAULT_SEVERITY_SCORES = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.55,
    "low": 0.3,
    "info": 0.1,
}
DEFAULT_THRESHOLDS = {"critical": 80.0, "high": 60.0, "medium": 35.0}


@dataclass(frozen=True)
class FindingRiskContext:
    """资产和环境风险上下文；没有上下文时由规则安全推断默认值。"""

    exploitability: float | None = None
    internet_exposure: float | None = None
    asset_criticality: float | None = None
    data_sensitivity: float | None = None
    dependency_reachability: float | None = None
    exploit_maturity: float | None = None
    fix_availability: float | None = None
    age_days: float | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "FindingRiskContext":
        if not isinstance(value, Mapping):
            return cls()
        return cls(
            exploitability=_optional_float(value.get("exploitability")),
            internet_exposure=_optional_float(value.get("internet_exposure")),
            asset_criticality=_optional_float(value.get("asset_criticality")),
            data_sensitivity=_optional_float(value.get("data_sensitivity")),
            dependency_reachability=_optional_float(value.get("dependency_reachability")),
            exploit_maturity=_optional_float(value.get("exploit_maturity")),
            fix_availability=_optional_float(value.get("fix_availability")),
            age_days=_optional_float(value.get("age_days")),
        )


@dataclass(frozen=True)
class RiskFactor:
    """一个可解释风险因子的归一化值、权重和贡献。"""

    name: str
    value: float
    weight: float
    contribution: float
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "weight": round(self.weight, 4),
            "contribution": round(self.contribution, 4),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class RiskScore:
    """风险评分结果，不依赖 LLM，能够追溯到每个计算因子。"""

    score: float
    priority: str
    factors: tuple[RiskFactor, ...]
    explanation: str
    policy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "priority": self.priority,
            "factors": [factor.to_dict() for factor in self.factors],
            "explanation": self.explanation,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class RiskPolicy:
    """风险策略；权重会在构造时归一化，避免配置错误放大分数。"""

    version: str = "risk-v1"
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    severity_scores: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SEVERITY_SCORES))
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "RiskPolicy":
        if not isinstance(value, Mapping):
            return cls()
        weights = _normalized_weights(value.get("weights"))
        severity_scores = _merged_scores(DEFAULT_SEVERITY_SCORES, value.get("severity_scores"))
        thresholds = _merged_thresholds(value.get("thresholds"))
        version = str(value.get("version", "risk-v1")).strip() or "risk-v1"
        return cls(version=version[:100], weights=weights, severity_scores=severity_scores, thresholds=thresholds)


def score_finding(
    finding: object,
    *,
    context: FindingRiskContext | Mapping[str, object] | None = None,
    policy: RiskPolicy | None = None,
    now: datetime | None = None,
) -> RiskScore:
    """基于确定性策略计算 Finding 风险分数和优先级。"""
    active_policy = policy or RiskPolicy()
    active_context = (
        context
        if isinstance(context, FindingRiskContext)
        else FindingRiskContext.from_mapping(context)
    )
    severity = _finding_value(finding, "severity", "medium").lower()
    category = _finding_value(finding, "category", "sast").lower()
    confidence = _clamp(_finding_float(finding, "confidence", 1.0))
    inferred = _infer_context(finding, category, severity, active_context, now)
    values = {
        "severity": _clamp(active_policy.severity_scores.get(severity, 0.4)),
        "confidence": confidence,
        "exploitability": _clamp(inferred.exploitability if inferred.exploitability is not None else 0.5),
        "internet_exposure": _clamp(inferred.internet_exposure if inferred.internet_exposure is not None else 0.5),
        "asset_criticality": _clamp(inferred.asset_criticality if inferred.asset_criticality is not None else 0.5),
        "data_sensitivity": _clamp(inferred.data_sensitivity if inferred.data_sensitivity is not None else 0.5),
        "dependency_reachability": _clamp(
            inferred.dependency_reachability if inferred.dependency_reachability is not None else 0.5
        ),
        "exploit_maturity": _clamp(inferred.exploit_maturity if inferred.exploit_maturity is not None else 0.5),
        "fix_availability": _clamp(inferred.fix_availability if inferred.fix_availability is not None else 0.5),
        "age": _age_score(inferred.age_days),
    }
    explanations = _factor_explanations(values, severity, category)
    factors = tuple(
        RiskFactor(
            name=name,
            value=values[name],
            weight=active_policy.weights.get(name, 0.0),
            contribution=values[name] * active_policy.weights.get(name, 0.0),
            explanation=explanations[name],
        )
        for name in FACTOR_NAMES
    )
    score = round(min(100.0, max(0.0, sum(factor.contribution for factor in factors) * 100)), 2)
    priority = _priority(score, active_policy.thresholds)
    top_factors = sorted(factors, key=lambda factor: factor.contribution, reverse=True)[:3]
    explanation = "风险分数 {:.2f}/100，优先级为 {}；主要因素：{}。".format(
        score,
        priority,
        "、".join(factor.name for factor in top_factors),
    )
    return RiskScore(score, priority, factors, explanation, active_policy.version)


def policy_from_config(config: Mapping[str, object] | None) -> RiskPolicy:
    """从 Flask 配置读取可选策略；非法配置安全回退默认策略。"""
    if not isinstance(config, Mapping):
        return RiskPolicy()
    raw = config.get("SECURITY_RISK_POLICY")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return RiskPolicy()
    return RiskPolicy.from_mapping(raw if isinstance(raw, Mapping) else None)


def _infer_context(
    finding: object,
    category: str,
    severity: str,
    context: FindingRiskContext,
    now: datetime | None,
) -> FindingRiskContext:
    has_cve = bool(_finding_value(finding, "cve_id", "").strip())
    severity_level = DEFAULT_SEVERITY_SCORES.get(severity, 0.4)
    age_days = context.age_days
    if age_days is None:
        created_at = getattr(finding, "created_at", None)
        age_days = _calculate_age_days(created_at, now)
    return FindingRiskContext(
        exploitability=context.exploitability if context.exploitability is not None else min(1.0, 0.35 + severity_level * 0.5),
        internet_exposure=context.internet_exposure,
        asset_criticality=context.asset_criticality,
        data_sensitivity=context.data_sensitivity if context.data_sensitivity is not None else (0.85 if category == "secret" else 0.5),
        dependency_reachability=context.dependency_reachability if context.dependency_reachability is not None else (0.7 if category == "sca" else 0.5),
        exploit_maturity=context.exploit_maturity if context.exploit_maturity is not None else (0.7 if has_cve else 0.35),
        fix_availability=context.fix_availability if context.fix_availability is not None else (0.65 if has_cve else 0.5),
        age_days=age_days,
    )


def _factor_explanations(values: dict[str, float], severity: str, category: str) -> dict[str, str]:
    return {
        "severity": f"Finding 严重等级为 {severity}。",
        "confidence": f"检测置信度为 {values['confidence']:.2f}。",
        "exploitability": f"根据 {category} 类别和严重等级推断可利用性为 {values['exploitability']:.2f}。",
        "internet_exposure": f"互联网暴露程度为 {values['internet_exposure']:.2f}。",
        "asset_criticality": f"资产重要性为 {values['asset_criticality']:.2f}。",
        "data_sensitivity": f"数据敏感度为 {values['data_sensitivity']:.2f}。",
        "dependency_reachability": f"依赖可达性为 {values['dependency_reachability']:.2f}。",
        "exploit_maturity": f"公开利用成熟度为 {values['exploit_maturity']:.2f}。",
        "fix_availability": f"修复紧迫度为 {values['fix_availability']:.2f}，数值越高表示越需要尽快处置。",
        "age": f"Finding 年龄因子为 {values['age']:.2f}。",
    }


def _priority(score: float, thresholds: Mapping[str, float]) -> str:
    if score >= thresholds.get("critical", 80.0):
        return "critical"
    if score >= thresholds.get("high", 60.0):
        return "high"
    if score >= thresholds.get("medium", 35.0):
        return "medium"
    return "low"


def _age_score(age_days: float | None) -> float:
    if age_days is None:
        return 0.5
    return _clamp(age_days / 365.0)


def _calculate_age_days(created_at: object, now: datetime | None) -> float | None:
    if not isinstance(created_at, datetime):
        return None
    current = now or datetime.now(timezone.utc)
    if created_at.tzinfo is None and current.tzinfo is not None:
        current = current.replace(tzinfo=None)
    elif created_at.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (current - created_at).total_seconds() / 86400)


def _normalized_weights(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return dict(DEFAULT_WEIGHTS)
    values = {name: 0.0 for name in FACTOR_NAMES}
    for name in FACTOR_NAMES:
        if name in value:
            try:
                values[name] = max(0.0, float(value[name]))
            except (TypeError, ValueError):
                pass
    total = sum(values.values())
    return dict(DEFAULT_WEIGHTS) if total <= 0 else {name: values[name] / total for name in FACTOR_NAMES}


def _merged_scores(defaults: Mapping[str, float], value: object) -> dict[str, float]:
    result = dict(defaults)
    if isinstance(value, Mapping):
        for name in result:
            try:
                result[name] = _clamp(float(value.get(name, result[name])))
            except (TypeError, ValueError):
                pass
    return result


def _merged_thresholds(value: object) -> dict[str, float]:
    result = dict(DEFAULT_THRESHOLDS)
    if isinstance(value, Mapping):
        for name in result:
            try:
                result[name] = min(100.0, max(0.0, float(value.get(name, result[name]))))
            except (TypeError, ValueError):
                pass
    return result


def _finding_value(finding: object, name: str, default: str) -> str:
    value = getattr(finding, name, default)
    value = getattr(value, "value", value)
    return str(value if value is not None else default).strip() or default


def _finding_float(finding: object, name: str, default: float) -> float:
    try:
        return float(getattr(finding, name, default))
    except (TypeError, ValueError):
        return default


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
