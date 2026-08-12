# -*- coding: utf-8 -*-
"""T06 强制基线与完成条件测试：基线不可删除、模式完成条件、模式禁止工具。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.plan_validator import (
    PlanValidationError,
    validate_envelope,
)
from app.services.security_agent.planning.completion_criteria import (
    CompletionCriteria,
    MANDATORY_BASELINE_KEYS,
)
from app.services.security_agent.planning.plan_service import (
    PlanService,
    PlanServiceError,
)


def _baseline_envelope() -> dict:
    return {
        "objective": "检查越权",
        "nodes": [
            {"key": "inventory", "type": "inventory", "title": "清点", "tool_name": "inventory_snapshot"},
            {"key": "baseline_scan", "type": "baseline_scan", "title": "扫描", "tool_name": "run_baseline_scan"},
            {"key": "auth_map", "type": "repository_mapping", "title": "鉴权", "tool_name": "get_authentication_map"},
        ],
        "edges": [{"from": "inventory", "to": "baseline_scan"}],
        "completion_criteria": ["inventory 完成", "baseline_scan 完成"],
    }


def test_mandatory_baseline_keys_frozen():
    assert MANDATORY_BASELINE_KEYS == frozenset({"inventory", "baseline_scan"})


def test_completion_criteria_per_mode():
    baseline = CompletionCriteria.for_mode("baseline")
    hybrid = CompletionCriteria.for_mode("hybrid")
    deep = CompletionCriteria.for_mode("deep_audit")
    assert MANDATORY_BASELINE_KEYS <= set(baseline.mandatory_node_keys)
    assert MANDATORY_BASELINE_KEYS <= set(hybrid.mandatory_node_keys)
    assert MANDATORY_BASELINE_KEYS <= set(deep.mandatory_node_keys)
    assert {"coverage_analysis", "risk_ranking"} <= set(hybrid.mandatory_node_keys)
    assert "report" in deep.mandatory_node_keys


def test_validator_accepts_baseline_envelope():
    envelope = _baseline_envelope()
    validated = validate_envelope(
        envelope,
        available_tools={
            "inventory_snapshot",
            "run_baseline_scan",
            "get_authentication_map",
        },
    )
    assert validated["objective"] == "检查越权"


def test_validator_rejects_envelope_without_baseline():
    envelope = _baseline_envelope()
    envelope["nodes"] = envelope["nodes"][2:]
    with pytest.raises(PlanValidationError):
        validate_envelope(
            envelope,
            available_tools={"get_authentication_map"},
        )


def test_validator_rejects_unknown_tool():
    envelope = _baseline_envelope()
    envelope["nodes"][2]["tool_name"] = "run_arbitrary_shell"
    with pytest.raises(PlanValidationError):
        validate_envelope(
            envelope,
            available_tools={"inventory_snapshot", "run_baseline_scan", "get_authentication_map"},
        )


def test_validator_rejects_tool_not_allowed_in_mode(app):
    """模式禁止工具：deep_audit 下不允许 baseline_only 工具被计划引用。"""
    envelope = _baseline_envelope()
    envelope["nodes"][2]["tool_name"] = "baseline_only_tool"
    with pytest.raises(PlanValidationError):
        validate_envelope(
            envelope,
            available_tools={
                "inventory_snapshot",
                "run_baseline_scan",
                "baseline_only_tool",
            },
            tool_allowed_modes={
                "inventory_snapshot": {"baseline", "hybrid", "deep_audit"},
                "run_baseline_scan": {"baseline", "hybrid", "deep_audit"},
                "baseline_only_tool": {"baseline"},
            },
            run_mode="deep_audit",
        )


def test_plan_patch_cannot_remove_mandatory_baseline_via_service(app):
    from app.models.agent_runtime import (
        AgentPlan,
        AgentPlanNode,
        AgentPlanNodeStatus,
        AgentPlanNodeType,
    )

    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="基线测试",
            mode="hybrid",
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="基线测试",
        )
        db.session.add(plan)
        db.session.flush()
        for key, node_type in (
            ("inventory", AgentPlanNodeType.INVENTORY.value),
            ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value),
        ):
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=key,
                    node_type=node_type,
                    status=AgentPlanNodeStatus.SUCCEEDED.value,
                    title=key,
                    tool_name=key,
                )
            )
        db.session.commit()
        with pytest.raises(PlanServiceError):
            PlanService().apply_patch(
                run,
                plan,
                patch={"remove_nodes": ["inventory"]},
                reason_code="forbidden",
                decision_type="auto",
                trace_id="t-baseline",
            )
