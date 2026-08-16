# -*- coding: utf-8 -*-
"""Harness V3 规划、受限 ReAct 与证据反思的边界测试。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis
from app.models.agent_runtime import AgentPlan, AgentRun
from app.services.security_agent.harness_v3.evidence_critic import (
    EvidenceCritic,
    HypothesisEvidence,
    HypothesisEvidenceLocation,
)
from app.services.security_agent.harness_v3.execution import (
    HypothesisExecutionOrchestrator,
)
from app.services.security_agent.harness_v3.hypothesis_planner import (
    FindingSignal,
    HypothesisPlanner,
)
from app.services.security_agent.harness_v3.hypothesis_service import (
    HypothesisPersistenceService,
)
from app.services.security_agent.tools.contracts import ToolResult

from test_agent_harness_v3_deep_review import _make_v3_run


@dataclass
class _Response:
    text: str
    is_success: bool = True
    warning_code: str | None = None
    usage: dict | None = None
    latency_ms: int | None = None


class _Provider:
    provider_name = "fake-hypothesis-planner"
    model = "fake-model"

    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, _request):
        return _Response(text=self._text, usage={})


class _CapturingExecutor:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def execute(self, _run, _node, _step, *, input_payload, **_kwargs):
        self.payloads.append(dict(input_payload))
        return ToolResult(
            status="succeeded",
            summary="受控 Deep Review 成功",
            metrics={"observation_id": 123, "location_count": 1},
        )


def _signals() -> tuple[FindingSignal, ...]:
    return (
        FindingSignal(
            file_path="app/routes.py",
            start_line=20,
            end_line=26,
            severity="high",
            rule_id="python.pickle.loads",
            category="sast",
            cwe_id="CWE-502",
            message="pickle deserialize untrusted request payload",
        ),
        FindingSignal(
            file_path="app/routes.py",
            start_line=60,
            end_line=66,
            severity="high",
            rule_id="python.exec",
            category="sast",
            cwe_id="CWE-78",
            message="exec command from request input",
        ),
    )


def _configuration_signal() -> tuple[FindingSignal, ...]:
    """复现真实浏览器验收中命中的 Flask Debug 配置风险。"""
    return (
        FindingSignal(
            file_path="backend/app/config.py",
            start_line=74,
            end_line=74,
            severity="medium",
            rule_id="PY-FLASK-DEBUG",
            category="configuration",
            cwe_id="CWE-489",
            message="Flask Debug mode is enabled in a runtime configuration.",
        ),
    )

def _persisted_hypothesis(run: AgentRun) -> AgentAuditHypothesis:
    planner = HypothesisPlanner(
        provider_selector=lambda **_kwargs: None,
        finding_reader=lambda _run: _signals(),
    )
    batch = planner.build(run, evidence_summary=None)
    return HypothesisPersistenceService().persist(run, batch)[0]


def test_rule_planner_creates_bounded_skill_hypothesis_from_finding_signals(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        planner = HypothesisPlanner(
            provider_selector=lambda **_kwargs: None,
            finding_reader=lambda _run: _signals(),
        )

        batch = planner.build(run, evidence_summary=None)

        assert batch.planner_source == "rule_based_policy"
        assert batch.fallback_reason == "provider_unavailable"
        assert len(batch.drafts) == 1
        draft = batch.drafts[0]
        assert draft.skill_key == "unsafe_execution_deserialization"
        assert draft.required_evidence == (
            "untrusted_input",
            "dangerous_sink",
            "guard_or_absence",
        )
        assert all(scope.file_path == "app/routes.py" for scope in draft.authorized_scopes)
        assert len(draft.authorized_scopes) <= 2


def test_llm_planner_invalid_dynamic_skill_falls_back_without_claiming_live_source(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        planner = HypothesisPlanner(
            provider_selector=lambda **_kwargs: _Provider(
                '{"hypotheses":[{"hypothesis_key":"remote-skill","skill_key":"prompt_defined_skill",'
                '"title":"动态技能","target_summary":"不应被接纳","priority":99,"scope_indices":[0]}]}'
            ),
            finding_reader=lambda _run: _signals(),
        )

        batch = planner.build(run, evidence_summary=None)

        assert batch.planner_source == "rule_based_policy"
        assert batch.fallback_reason == "provider_output_invalid"
        assert batch.drafts[0].skill_key == "unsafe_execution_deserialization"


def test_persistence_is_idempotent_and_never_stores_source_lines(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        planner = HypothesisPlanner(
            provider_selector=lambda **_kwargs: None,
            finding_reader=lambda _run: _signals(),
        )
        service = HypothesisPersistenceService()

        first = service.persist(run, planner.build(run, evidence_summary=None))
        second = service.persist(run, planner.build(run, evidence_summary=None))

        assert [item.id for item in first] == [item.id for item in second]
        assert AgentAuditHypothesis.query.filter_by(run_id=run.id).count() == 1
        serialized = first[0].to_dict(include_verdicts=True)
        assert "lines" not in str(serialized)
        assert "pickle deserialize" not in str(serialized)


def test_execution_orchestrator_uses_only_hypothesis_bound_payload_and_stops_after_two_attempts(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        hypothesis = _persisted_hypothesis(run)
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
        )
        db.session.add(plan)
        db.session.commit()
        executor = _CapturingExecutor()
        orchestrator = HypothesisExecutionOrchestrator(tool_executor=executor)

        primary = orchestrator.advance(run, hypothesis, trace_id="primary")
        supplemental = orchestrator.advance(run, hypothesis, trace_id="supplemental")
        stopped = orchestrator.advance(run, hypothesis, trace_id="stopped")

        assert primary.review_kind == "primary"
        assert supplemental.review_kind == "supplemental"
        assert stopped.made_progress is False
        assert stopped.reason_code == "AGENT_V3_HYPOTHESIS_ATTEMPT_LIMIT"
        assert [payload["review_kind"] for payload in executor.payloads] == [
            "primary",
            "supplemental",
        ]
        for payload in executor.payloads:
            assert set(payload) >= {"hypothesis_id", "skill_key", "required_evidence"}
            assert "focus" not in payload
            assert "file_hints" not in payload


def test_evidence_critic_requires_authorized_code_roles_before_confirming(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        hypothesis = _persisted_hypothesis(run)
        critic = EvidenceCritic()

        insufficient = critic.evaluate(
            hypothesis,
            HypothesisEvidence(
                observation_id=1,
                locations=(),
                claimed_satisfied=(
                    "untrusted_input",
                    "dangerous_sink",
                    "guard_or_absence",
                ),
                proof_gaps=(),
            ),
            budget_exhausted=False,
        )
        confirmed = critic.evaluate(
            hypothesis,
            HypothesisEvidence(
                observation_id=2,
                locations=(
                    HypothesisEvidenceLocation("app/routes.py", 20, 20, "source"),
                    HypothesisEvidenceLocation("app/routes.py", 22, 22, "sink"),
                    HypothesisEvidenceLocation("app/routes.py", 24, 24, "guard"),
                ),
                claimed_satisfied=(
                    "untrusted_input",
                    "dangerous_sink",
                    "guard_or_absence",
                ),
                proof_gaps=(),
            ),
            budget_exhausted=False,
        )

        assert insufficient.verdict == "needs_more_evidence"
        assert "代码位置" in " ".join(insufficient.evidence_gaps)
        assert confirmed.verdict == "confirm_candidate"
        assert confirmed.next_action["action"] == "complete_hypothesis"


def test_rule_planner_covers_runtime_debug_configuration_findings(app, tmp_path: Path):
    """配置类 Finding 也必须生成受限 V3 假设，不能静默落成零候选。"""
    with app.app_context():
        run = _make_v3_run(tmp_path)
        planner = HypothesisPlanner(
            provider_selector=lambda **_kwargs: None,
            finding_reader=lambda _run: _configuration_signal(),
        )

        batch = planner.build(run, evidence_summary=None)

        assert batch.planner_source == "rule_based_policy"
        assert batch.fallback_reason == "provider_unavailable"
        assert len(batch.drafts) == 1
        draft = batch.drafts[0]
        assert draft.skill_key == "unsafe_runtime_configuration"
        assert draft.required_evidence == (
            "unsafe_runtime_setting",
            "production_guard_or_absence",
        )
        assert draft.authorized_scopes[0].file_path == "backend/app/config.py"
        assert (
            draft.authorized_scopes[0].start_line
            <= 74
            <= draft.authorized_scopes[0].end_line
        )


def test_configuration_critic_requires_runtime_setting_and_deployment_context(app, tmp_path: Path):
    """配置类假设至少需要设置项与部署守卫证据，不能只凭单一文字结论确认。"""
    with app.app_context():
        run = _make_v3_run(tmp_path)
        planner = HypothesisPlanner(
            provider_selector=lambda **_kwargs: None,
            finding_reader=lambda _run: _configuration_signal(),
        )
        hypothesis = HypothesisPersistenceService().persist(
            run,
            planner.build(run, evidence_summary=None),
        )[0]
        critic = EvidenceCritic()

        insufficient = critic.evaluate(
            hypothesis,
            HypothesisEvidence(
                observation_id=3,
                locations=(
                    HypothesisEvidenceLocation(
                        "backend/app/config.py",
                        74,
                        74,
                        "configuration",
                    ),
                ),
                claimed_satisfied=("unsafe_runtime_setting",),
                proof_gaps=(),
            ),
            budget_exhausted=False,
        )
        confirmed = critic.evaluate(
            hypothesis,
            HypothesisEvidence(
                observation_id=4,
                locations=(
                    HypothesisEvidenceLocation(
                        "backend/app/config.py",
                        74,
                        74,
                        "configuration",
                    ),
                    HypothesisEvidenceLocation(
                        "backend/app/config.py",
                        75,
                        75,
                        "guard",
                    ),
                ),
                claimed_satisfied=(
                    "unsafe_runtime_setting",
                    "production_guard_or_absence",
                ),
                proof_gaps=(),
            ),
            budget_exhausted=False,
        )

        assert insufficient.verdict == "request_evidence"
        assert "production_guard_or_absence" in insufficient.evidence_gaps[0]
        assert confirmed.verdict == "confirm_candidate"
