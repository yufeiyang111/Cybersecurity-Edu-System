# -*- coding: utf-8 -*-
"""T08 CompletionEvaluator 测试：五种终态与过早 Final Answer 判定。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
)
from app.services.security_agent.loop.completion_evaluator import (
    CompletionEvaluator,
    CompletionVerdict,
)


def _make_run_and_plan(app, *, mode="hybrid", statuses=None, warnings=()):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="完成测试",
            mode=mode,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="完成测试",
        )
        db.session.add(plan)
        db.session.flush()
        defaults = {
            "inventory": AgentPlanNodeStatus.SUCCEEDED.value,
            "baseline_scan": AgentPlanNodeStatus.SUCCEEDED.value,
            "coverage_analysis": AgentPlanNodeStatus.SUCCEEDED.value,
            "risk_ranking": AgentPlanNodeStatus.SUCCEEDED.value,
        }
        for key, node_type in (
            ("inventory", AgentPlanNodeType.INVENTORY.value),
            ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value),
            ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value),
            ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value),
        ):
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=key,
                    node_type=node_type,
                    status=(statuses or defaults).get(
                        key, AgentPlanNodeStatus.SUCCEEDED.value
                    ),
                    title=key,
                    tool_name=key,
                )
            )
        if warnings:
            run.warning_codes = list(warnings)
        db.session.commit()
        return run.id, plan.id


def _evaluate(app, run_id, plan_id, *, evidence=None, model_final=None):
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        return CompletionEvaluator().evaluate(
            run, plan, evidence=evidence, model_final=model_final
        )


def test_completed_when_all_requirements_met(app):
    run_id, plan_id = _make_run_and_plan(app)
    verdict = _evaluate(app, run_id, plan_id, model_final="总结完成")
    assert verdict.accepted is True
    assert verdict.terminal_status == "completed"
    assert verdict.missing_requirements == ()


def test_completed_with_warnings_when_warning_codes_present(app):
    run_id, plan_id = _make_run_and_plan(
        app, warnings=("AGENT_PROVIDER_TIMEOUT",)
    )
    verdict = _evaluate(app, run_id, plan_id, model_final="总结完成")
    assert verdict.accepted is True
    assert verdict.terminal_status == "completed_with_warnings"
    assert "AGENT_PROVIDER_TIMEOUT" in verdict.warning_codes


def test_partial_when_mandatory_node_missing(app):
    statuses = {
        "inventory": AgentPlanNodeStatus.SUCCEEDED.value,
        "baseline_scan": AgentPlanNodeStatus.SUCCEEDED.value,
        "coverage_analysis": AgentPlanNodeStatus.PENDING.value,
        "risk_ranking": AgentPlanNodeStatus.SUCCEEDED.value,
    }
    run_id, plan_id = _make_run_and_plan(app, statuses=statuses)
    verdict = _evaluate(app, run_id, plan_id, model_final="总结完成")
    assert verdict.accepted is False
    assert verdict.terminal_status == "partial"
    assert "coverage_analysis" in verdict.missing_requirements


def test_failed_when_mandatory_baseline_failed(app):
    statuses = {
        "inventory": AgentPlanNodeStatus.SUCCEEDED.value,
        "baseline_scan": AgentPlanNodeStatus.FAILED.value,
        "coverage_analysis": AgentPlanNodeStatus.SUCCEEDED.value,
        "risk_ranking": AgentPlanNodeStatus.SUCCEEDED.value,
    }
    run_id, plan_id = _make_run_and_plan(app, statuses=statuses)
    verdict = _evaluate(app, run_id, plan_id, model_final="总结完成")
    assert verdict.accepted is False
    assert verdict.terminal_status == "failed"
    assert "baseline_scan" in verdict.missing_requirements


def test_failed_when_budget_exhausted_and_plan_incomplete(app):
    statuses = {
        "inventory": AgentPlanNodeStatus.SUCCEEDED.value,
        "baseline_scan": AgentPlanNodeStatus.SUCCEEDED.value,
        "coverage_analysis": AgentPlanNodeStatus.PENDING.value,
        "risk_ranking": AgentPlanNodeStatus.SUCCEEDED.value,
    }
    run_id, plan_id = _make_run_and_plan(app, statuses=statuses)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        run.max_tool_calls = 2
        run.tool_call_count = 2
        db.session.commit()
    verdict = _evaluate(app, run_id, plan_id, model_final="总结完成")
    assert verdict.accepted is False
    assert verdict.terminal_status == "partial"
    assert any("budget" in requirement for requirement in verdict.missing_requirements)


def test_early_final_answer_rejected_with_missing_requirements(app):
    statuses = {
        "inventory": AgentPlanNodeStatus.SUCCEEDED.value,
        "baseline_scan": AgentPlanNodeStatus.SUCCEEDED.value,
        "coverage_analysis": AgentPlanNodeStatus.PENDING.value,
        "risk_ranking": AgentPlanNodeStatus.PENDING.value,
    }
    run_id, plan_id = _make_run_and_plan(app, statuses=statuses)
    verdict = _evaluate(app, run_id, plan_id, model_final="过早总结")
    assert verdict.accepted is False
    assert verdict.terminal_status == "partial"
    assert len(verdict.missing_requirements) >= 2


def test_verdict_is_frozen_dataclass():
    verdict = CompletionVerdict(
        accepted=True,
        terminal_status="completed",
        missing_requirements=(),
        warning_codes=(),
        completion_reason="ok",
    )
    assert verdict.accepted is True
    assert verdict.completion_reason == "ok"
