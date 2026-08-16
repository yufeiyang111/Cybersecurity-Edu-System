# -*- coding: utf-8 -*-
"""Harness V3 协调器的状态机与旧自由 Deep Review 隔离测试。"""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanEdge,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRunStatus,
)
from app.services.security_agent.evidence_evaluator import EvidenceSummary
from app.services.security_agent.harness_v3.hypothesis_planner import HypothesisPlanBatch
from app.services.security_agent.harness_v3.coordinator import HarnessV3Coordinator
from app.services.security_agent.tools.contracts import ToolResult

from test_agent_harness_v3_deep_review import _make_v3_run


class _Lease:
    def __init__(self) -> None:
        self.released = False

    @staticmethod
    def acquire(_run_id, _owner, *, lease_seconds):
        assert lease_seconds > 0
        return True

    @staticmethod
    def heartbeat(_run_id, _owner):
        return None

    def release(self, _run_id, _owner):
        self.released = True


class _Tools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, _run, node, _step, *, input_payload, **_kwargs):
        self.calls.append((node.tool_name, dict(input_payload or {})))
        return ToolResult(status="succeeded", summary="测试工具成功")


class _NoHypothesisPlanner:
    @staticmethod
    def build(_run, *, evidence_summary):
        assert isinstance(evidence_summary, EvidenceSummary)
        return HypothesisPlanBatch(
            drafts=(),
            planner_source="rule_based_policy",
            fallback_reason="no_matching_finding_signals",
            finding_signals=(),
        )


class _EvidenceEvaluator:
    @staticmethod
    def evaluate(_run, _plan):
        return EvidenceSummary()


def _plan_with_legacy_deep_review(run):
    plan = AgentPlan(
        run_id=run.id,
        plan_version=1,
        planner_source="rule_based_policy",
    )
    db.session.add(plan)
    db.session.flush()
    legacy_deep_review = AgentPlanNode(
        plan_id=plan.id,
        node_key="deep_review",
        node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
        status=AgentPlanNodeStatus.READY.value,
        title="旧版自由深度审查",
        tool_name="run_deep_review",
        input_json={"focus": "不允许由 V3 执行的自由焦点"},
    )
    report = AgentPlanNode(
        plan_id=plan.id,
        node_key="report",
        node_type=AgentPlanNodeType.REPORT_GENERATION.value,
        status=AgentPlanNodeStatus.PENDING.value,
        title="生成摘要",
        tool_name="finalize_agent_report",
    )
    edge = AgentPlanEdge(
        plan_id=plan.id,
        from_node="deep_review",
        to_node="report",
        edge_type=AgentPlanEdgeType.SUCCESS.value,
    )
    db.session.add_all([legacy_deep_review, report, edge])
    db.session.commit()
    return plan, legacy_deep_review, report


def test_v3_coordinator_skips_legacy_free_focus_and_finalizes_report(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        plan, legacy_deep_review, report = _plan_with_legacy_deep_review(run)
        tools = _Tools()
        lease = _Lease()
        coordinator = HarnessV3Coordinator(
            tool_executor=tools,
            hypothesis_planner=_NoHypothesisPlanner(),
            evidence_evaluator=_EvidenceEvaluator(),
            leases=lease,
        )

        result = coordinator.run_hybrid_or_deep(run.id, "v3-coordinator")

        run = db.session.get(type(run), run.id)
        legacy_deep_review = db.session.get(type(legacy_deep_review), legacy_deep_review.id)
        report = db.session.get(type(report), report.id)
        assert result == AgentRunStatus.COMPLETED.value
        assert run.status == AgentRunStatus.COMPLETED.value
        assert legacy_deep_review.status == AgentPlanNodeStatus.SKIPPED.value
        assert report.status == AgentPlanNodeStatus.SUCCEEDED.value
        assert tools.calls == [("finalize_agent_report", {})]
        assert lease.released is True
        assert plan.id == report.plan_id
