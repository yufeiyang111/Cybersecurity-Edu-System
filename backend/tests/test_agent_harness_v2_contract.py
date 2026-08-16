# -*- coding: utf-8 -*-
"""Agent Harness V2 阶段 1：状态、终态和统计契约的边界测试。"""
from __future__ import annotations

from pathlib import Path

from app import db
from app.scripts.apply_sql_migration import MIGRATION_IDS
from app.models.agent_approval import AgentApproval
from app.models.agent_review import AgentObservation, AgentObservationLocation
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
    AgentStepExecution,
    AgentToolCall,
)
from app.services.security_agent.loop.completion_evaluator import CompletionEvaluator
from app.services.security_agent.service import AgentRunService
from app.services.security_agent.state_machine import AgentStateMachine


def _make_plan(app, *, mode: str = "hybrid", node_statuses: dict[str, str] | None = None):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="阶段 1 契约测试",
            mode=mode,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="test",
            objective="阶段 1 契约测试",
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
                    status=(node_statuses or defaults).get(key, defaults[key]),
                    title=key,
                    tool_name=key,
                )
            )
        db.session.commit()
        return run.id, plan.id


def test_iteration_limit_with_usable_plan_is_completed_with_warnings(app):
    run_id, plan_id = _make_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        verdict = CompletionEvaluator().evaluate(
            run,
            plan,
            limit_code="AGENT_ITERATION_LIMIT_REACHED",
            evidence={"observations_count": 1},
        )

    assert verdict.accepted is True
    assert verdict.terminal_status == AgentRunStatus.COMPLETED_WITH_WARNINGS.value
    assert verdict.warning_codes == ("AGENT_ITERATION_LIMIT_REACHED",)


def test_iteration_limit_without_required_evidence_is_blocked(app):
    run_id, plan_id = _make_plan(app, mode="deep_audit")
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        db.session.add(
            AgentPlanNode(
                plan_id=plan.id,
                node_key="report_generation",
                node_type=AgentPlanNodeType.REPORT_GENERATION.value,
                status=AgentPlanNodeStatus.SUCCEEDED.value,
                title="report_generation",
                tool_name="report_generation",
            )
        )
        db.session.commit()
        db.session.refresh(plan)
        verdict = CompletionEvaluator().evaluate(
            run,
            plan,
            limit_code="AGENT_ITERATION_LIMIT_REACHED",
            evidence={"observations_count": 0},
        )

    assert verdict.accepted is False
    assert verdict.terminal_status == AgentRunStatus.BLOCKED.value
    assert "evidence_insufficient" in verdict.missing_requirements
    assert "AGENT_ITERATION_LIMIT_REACHED" in verdict.warning_codes


def test_deep_audit_requires_completed_deep_review_even_with_observation(app):
    """已有 Observation 也不能掩盖计划中尚未执行的强制深度审查节点。"""
    run_id, plan_id = _make_plan(app, mode="deep_audit")
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        db.session.add_all(
            [
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key="deep_review",
                    node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
                    status=AgentPlanNodeStatus.PENDING.value,
                    title="deep_review",
                    tool_name="run_deep_review",
                ),
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key="report",
                    node_type=AgentPlanNodeType.REPORT_GENERATION.value,
                    status=AgentPlanNodeStatus.SUCCEEDED.value,
                    title="report",
                    tool_name="finalize_agent_report",
                ),
            ]
        )
        db.session.commit()
        db.session.refresh(plan)
        verdict = CompletionEvaluator().evaluate(
            run,
            plan,
            evidence={"observations_count": 1},
        )

    assert verdict.accepted is False
    assert verdict.terminal_status == AgentRunStatus.PARTIAL.value
    assert "deep_review" in verdict.missing_requirements


def test_deep_audit_completes_after_deep_review_and_observation(app):
    """Deep Audit 必须同时具备已完成的审查节点与可核验 Observation 才可交付。"""
    run_id, plan_id = _make_plan(app, mode="deep_audit")
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        db.session.add_all(
            [
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key="deep_review",
                    node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
                    status=AgentPlanNodeStatus.SUCCEEDED.value,
                    title="deep_review",
                    tool_name="run_deep_review",
                ),
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key="report",
                    node_type=AgentPlanNodeType.REPORT_GENERATION.value,
                    status=AgentPlanNodeStatus.SUCCEEDED.value,
                    title="report",
                    tool_name="finalize_agent_report",
                ),
            ]
        )
        db.session.commit()
        db.session.refresh(plan)
        verdict = CompletionEvaluator().evaluate(
            run,
            plan,
            evidence={"observations_count": 1},
        )

    assert verdict.accepted is True
    assert verdict.terminal_status == AgentRunStatus.COMPLETED.value

def test_cancel_requested_is_not_terminal_and_only_finishes_as_canceled(app):
    assert AgentStateMachine.can_transition(
        AgentRunStatus.EXECUTING_TOOLS.value,
        AgentRunStatus.CANCEL_REQUESTED.value,
    )
    assert AgentStateMachine.can_transition(
        AgentRunStatus.CANCEL_REQUESTED.value,
        AgentRunStatus.CANCELED.value,
    )
    assert not AgentStateMachine.can_transition(
        AgentRunStatus.EXECUTING_TOOLS.value,
        AgentRunStatus.CANCELED.value,
    )
    assert not AgentStateMachine.is_terminal(AgentRunStatus.CANCEL_REQUESTED.value)
    assert AgentStateMachine.is_terminal(AgentRunStatus.BLOCKED.value)


def test_run_detail_exposes_consistent_statistics(app):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="统计契约测试",
            mode="hybrid",
            iteration_count=3,
            replan_count=2,
            warning_codes=["AGENT_PROVIDER_TIMEOUT"],
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="test",
            objective="统计契约测试",
        )
        db.session.add(plan)
        db.session.flush()
        succeeded_node = AgentPlanNode(
            plan_id=plan.id,
            node_key="inventory",
            node_type=AgentPlanNodeType.INVENTORY.value,
            status=AgentPlanNodeStatus.SUCCEEDED.value,
            title="清点",
        )
        failed_node = AgentPlanNode(
            plan_id=plan.id,
            node_key="baseline_scan",
            node_type=AgentPlanNodeType.BASELINE_SCAN.value,
            status=AgentPlanNodeStatus.FAILED.value,
            title="基线扫描",
        )
        db.session.add_all([succeeded_node, failed_node])
        db.session.flush()
        db.session.add(
            AgentStepExecution(
                plan_node_id=succeeded_node.id,
                run_id=run.id,
                status="completed",
            )
        )
        db.session.add_all(
            [
                AgentToolCall(
                    run_id=run.id,
                    plan_node_id=succeeded_node.id,
                    tool_name="inventory",
                    status="succeeded",
                    idempotency_key="stats-success",
                ),
                AgentToolCall(
                    run_id=run.id,
                    plan_node_id=failed_node.id,
                    tool_name="scan",
                    status="failed",
                    idempotency_key="stats-failed",
                ),
            ]
        )
        observation = AgentObservation(
            run_id=run.id,
            title="可疑输入",
            summary="存在待核验输入",
            status="unverified",
            confidence="medium",
        )
        db.session.add(observation)
        db.session.flush()
        db.session.add(
            AgentObservationLocation(
                observation_id=observation.id,
                file_path="src/app.py",
                start_line=10,
                end_line=12,
                role="evidence",
            )
        )
        db.session.add(
            AgentApproval(
                run_id=run.id,
                workspace_id=run.workspace_id,
                operation_type="remediation_generation",
                reason="需要人工确认",
                operation_digest="stats-approval",
                status="pending",
            )
        )
        db.session.commit()

        payload = AgentRunService().get_run_payload(run)

    stats = payload["stats"]
    assert stats == {
        "plan_node_total": 2,
        "plan_node_completed": 1,
        "plan_node_failed": 1,
        "turn_total": 3,
        "tool_call_total": 2,
        "tool_call_succeeded": 1,
        "tool_call_failed": 1,
        "observation_total": 1,
        "observation_with_code_evidence": 1,
        "observation_unverified": 1,
        "replan_total": 2,
        "approval_pending": 1,
        "warning_total": 1,
    }


def test_state_contract_migration_and_init_sql_are_synced():
    repository_root = Path(__file__).resolve().parents[2]
    migration_path = (
        repository_root
        / "database"
        / "migrations"
        / "040_agent_harness_state_contract.sql"
    )
    migration_sql = migration_path.read_text(encoding="utf-8")
    init_sql = (repository_root / "database" / "init.sql").read_text(
        encoding="utf-8"
    )

    assert migration_path.is_file()
    assert "MODIFY COLUMN status ENUM" in migration_sql
    assert "'blocked'" in migration_sql
    assert "'cancel_requested'" in migration_sql
    assert "040_agent_harness_state_contract" in MIGRATION_IDS
    assert MIGRATION_IDS.index("040_agent_harness_state_contract") < MIGRATION_IDS.index("041_agent_run_feature_flags_snapshot")
    assert "'blocked', 'cancel_requested', 'partial'" in init_sql
    for forbidden in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert forbidden not in migration_sql