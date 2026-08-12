# -*- coding: utf-8 -*-
"""T06 Plan Patch 测试：追加/替换未完成节点、禁止改写历史与删除强制基线、幂等。"""
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
from app.services.security_agent.planning.plan_service import (
    PlanService,
    PlanServiceError,
)
from app.services.security_agent.strategy_catalog import NodeSpec


def _base_plan(app) -> tuple:
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="Patch 测试",
            mode="hybrid",
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="Patch 测试",
        )
        db.session.add(plan)
        db.session.flush()
        specs = [
            ("inventory", AgentPlanNodeType.INVENTORY.value, AgentPlanNodeStatus.SUCCEEDED.value),
            ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value, AgentPlanNodeStatus.SUCCEEDED.value),
            ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value, AgentPlanNodeStatus.PENDING.value),
            ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value, AgentPlanNodeStatus.PENDING.value),
            ("report", AgentPlanNodeType.REPORT_GENERATION.value, AgentPlanNodeStatus.PENDING.value),
        ]
        for key, node_type, status in specs:
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=key,
                    node_type=node_type,
                    status=status,
                    title=key,
                    tool_name={
                        "inventory": "inventory_snapshot",
                        "baseline_scan": "run_baseline_scan",
                        "coverage_analysis": "get_scan_coverage",
                        "risk_ranking": "rank_findings",
                        "report": "finalize_agent_report",
                    }[key],
                )
            )
        db.session.commit()
        return run.id, plan.id


def _spec(key: str, tool_name: str, *, depends_on=()) -> NodeSpec:
    return NodeSpec(
        key=key,
        node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
        title=key,
        description=key,
        tool_name=tool_name,
        depends_on=depends_on,
    )


def test_patch_appends_new_node(app):
    run_id, plan_id = _base_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        new_plan = PlanService().create_version(
            run,
            plan,
            node_specs=(_spec("auth_map", "get_authentication_map"),),
            reason_code="user_direction_extends_plan",
            decision_type="user_direction",
            decision_summary="追加鉴权分析",
            trace_id="t-patch",
        )
        assert new_plan.plan_version == 2
        keys = {node.node_key for node in new_plan.nodes}
        assert "auth_map" in keys
        assert "inventory" in keys
        assert "report" in keys


def test_patch_cannot_rewrite_completed_history(app):
    run_id, plan_id = _base_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        with pytest.raises(PlanServiceError):
            PlanService().apply_patch(
                run,
                plan,
                patch={
                    "replace_nodes": [
                        _spec("inventory", "inventory_snapshot"),
                    ]
                },
                reason_code="forbidden_rewrite",
                decision_type="auto",
                trace_id="t-rewrite",
            )


def test_patch_cannot_remove_mandatory_baseline(app):
    run_id, plan_id = _base_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        with pytest.raises(PlanServiceError):
            PlanService().apply_patch(
                run,
                plan,
                patch={
                    "remove_nodes": ["inventory", "baseline_scan"],
                },
                reason_code="forbidden_remove",
                decision_type="auto",
                trace_id="t-remove",
            )


def test_patch_replaces_unfinished_node(app):
    run_id, plan_id = _base_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        replacement = _spec("coverage_analysis", "get_scan_coverage")
        new_plan = PlanService().apply_patch(
            run,
            plan,
            patch={"replace_nodes": [replacement]},
            reason_code="strategy_switch",
            decision_type="auto",
            decision_summary="替换未完成的覆盖分析节点",
            trace_id="t-replace",
        )
        assert new_plan.plan_version == 2
        replaced = next(
            node for node in new_plan.nodes if node.node_key == "coverage_analysis"
        )
        assert replaced.status == AgentPlanNodeStatus.PENDING.value


def test_same_patch_is_idempotent(app):
    run_id, plan_id = _base_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        service = PlanService()
        first = service.create_version(
            run,
            plan,
            node_specs=(_spec("auth_map", "get_authentication_map"),),
            reason_code="user_direction_extends_plan",
            decision_type="user_direction",
            decision_summary="追加鉴权分析",
            trace_id="t-idem-1",
        )
        second = service.create_version(
            run,
            plan,
            node_specs=(_spec("auth_map", "get_authentication_map"),),
            reason_code="user_direction_extends_plan",
            decision_type="user_direction",
            decision_summary="追加鉴权分析",
            trace_id="t-idem-2",
        )
        assert second.id == first.id, "相同 patch 不得重复创建版本"


def test_plan_version_cap_rejects_overflow(app):
    run_id, plan_id = _base_plan(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        plan = db.session.get(AgentPlan, plan_id)
        service = PlanService()
        for index in range(2, 6):
            plan = service.create_version(
                run,
                plan,
                node_specs=(_spec(f"extra_{index}", "map_repository"),),
                reason_code="user_direction_extends_plan",
                decision_type="user_direction",
                decision_summary=f"版本 {index}",
                trace_id=f"t-cap-{index}",
            )
        assert plan.plan_version == 5
        overflow = service.create_version(
            run,
            plan,
            node_specs=(_spec("too_many", "map_repository"),),
            reason_code="user_direction_extends_plan",
            decision_type="user_direction",
            decision_summary="超限",
            trace_id="t-cap-overflow",
        )
        assert overflow is None
