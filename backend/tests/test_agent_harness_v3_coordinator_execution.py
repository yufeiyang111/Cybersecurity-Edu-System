# -*- coding: utf-8 -*-
"""Harness V3 真实假设执行与 Evidence Critic 集成测试。"""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.agent_items import AgentItem
from app.models.agent_hypothesis import AgentAuditHypothesis, AuditHypothesisStatus
from app.models.agent_review import (
    AgentObservation,
    AgentObservationLocation,
    ObservationConfidence,
    ObservationStatus,
)
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRunStatus,
)
from app.services.security_agent.evidence_evaluator import EvidenceSummary
from app.services.security_agent.harness_v3.coordinator import HarnessV3Coordinator
from app.services.security_agent.harness_v3.hypothesis_planner import HypothesisPlanBatch
from app.services.security_agent.hypotheses.contracts import (
    AuditHypothesisDraft,
    CodeLocationScope,
)
from app.services.security_agent.tools.contracts import ToolResult

from test_agent_harness_v3_deep_review import _make_v3_run


class _Lease:
    @staticmethod
    def acquire(_run_id, _owner, *, lease_seconds):
        return lease_seconds > 0

    @staticmethod
    def heartbeat(_run_id, _owner):
        return None

    @staticmethod
    def release(_run_id, _owner):
        return None


class _EvidenceEvaluator:
    @staticmethod
    def evaluate(_run, _plan):
        return EvidenceSummary()


class _HypothesisPlanner:
    @staticmethod
    def build(run, *, evidence_summary):
        assert isinstance(evidence_summary, EvidenceSummary)
        return HypothesisPlanBatch(
            drafts=(
                AuditHypothesisDraft(
                    hypothesis_key=f"unsafe_execution_deserialization-{run.id}",
                    skill_key="unsafe_execution_deserialization",
                    title="危险执行与反序列化验证候选",
                    target_summary="核验 app.py 授权窗口内的不可信输入、危险调用和防护位置。",
                    priority=90,
                    required_evidence=(
                        "untrusted_input",
                        "dangerous_sink",
                        "guard_or_absence",
                    ),
                    authorized_scopes=(CodeLocationScope("app.py", 10, 20),),
                    planner_source="rule_based_policy",
                ),
            ),
            planner_source="rule_based_policy",
            fallback_reason="test_fixture",
            finding_signals=(),
        )


class _ObservationTools:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def execute(self, run, node, _step, *, input_payload, **_kwargs):
        self.payloads.append({"tool_name": node.tool_name, "input": dict(input_payload or {})})
        if node.tool_name == "run_deep_review":
            observation = AgentObservation(
                run_id=run.id,
                title="受限候选",
                status=ObservationStatus.UNVERIFIED.value,
                confidence=ObservationConfidence.MEDIUM.value,
                summary="授权位置显示输入、危险调用和防护检查。",
                detail_json={
                    "v3_evidence_satisfied": [
                        "untrusted_input",
                        "dangerous_sink",
                        "guard_or_absence",
                    ],
                    "v3_control_assessments": {
                        "guard_or_absence": "absent",
                    },
                },
                proof_gaps_json=[],
            )
            db.session.add(observation)
            db.session.flush()
            db.session.add_all(
                [
                    AgentObservationLocation(
                        observation_id=observation.id,
                        file_path="app.py",
                        start_line=10,
                        end_line=10,
                        role="source",
                    ),
                    AgentObservationLocation(
                        observation_id=observation.id,
                        file_path="app.py",
                        start_line=12,
                        end_line=12,
                        role="sink",
                    ),

                ]
            )
            db.session.commit()
            return ToolResult(
                status="succeeded",
                summary="V3 主审完成",
                metrics={"observation_id": observation.id},
            )
        return ToolResult(status="succeeded", summary="报告生成完成")


def _report_plan(run):
    plan = AgentPlan(
        run_id=run.id,
        plan_version=1,
        planner_source="rule_based_policy",
    )
    db.session.add(plan)
    db.session.flush()
    report = AgentPlanNode(
        plan_id=plan.id,
        node_key="report",
        node_type=AgentPlanNodeType.REPORT_GENERATION.value,
        status=AgentPlanNodeStatus.READY.value,
        title="生成摘要",
        tool_name="finalize_agent_report",
    )
    db.session.add(report)
    db.session.commit()
    return plan


def test_v3_coordinator_confirms_candidate_only_after_authorized_role_evidence(app, tmp_path: Path):
    with app.app_context():
        lines = "\n".join(f"line-{index}" for index in range(1, 31)) + "\n"
        run = _make_v3_run(tmp_path, files={"app.py": lines})
        _report_plan(run)
        tools = _ObservationTools()
        coordinator = HarnessV3Coordinator(
            tool_executor=tools,
            hypothesis_planner=_HypothesisPlanner(),
            evidence_evaluator=_EvidenceEvaluator(),
            leases=_Lease(),
        )

        result = coordinator.run_hybrid_or_deep(run.id, "v3-critic-confirmation")

        hypothesis = AgentAuditHypothesis.query.filter_by(run_id=run.id).one()
        assert result == AgentRunStatus.COMPLETED.value
        assert hypothesis.status == AuditHypothesisStatus.CONFIRMED.value
        assert hypothesis.execution_attempt_count == 1
        assert hypothesis.reflection_count == 0
        assert len(hypothesis.verdicts) == 1
        assert hypothesis.verdicts[0].verdict == "confirm_candidate"
        review_payload = tools.payloads[0]["input"]
        assert tools.payloads[0]["tool_name"] == "run_deep_review"
        assert set(review_payload) == {
            "hypothesis_id",
            "skill_key",
            "required_evidence",
            "review_kind",
        }
        assert "focus" not in review_payload
        assert "file_hints" not in review_payload

        summaries = AgentItem.query.filter_by(
            run_id=run.id,
            item_type="reasoning_summary",
        ).all()
        assert len(summaries) == 2
        assert all(item.status == "completed" for item in summaries)
        assert all(
            set(item.summary_json) == {
                "hypothesis_id",
                "action_reason",
                "evidence_gap",
                "next_step",
                "sensitive_level",
            }
            for item in summaries
        )
        persisted_summary = " ".join(item.content_redacted or "" for item in summaries)
        assert "Provider 原始 reasoning" not in persisted_summary
        assert "line-10" not in persisted_summary
