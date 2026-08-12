# -*- coding: utf-8 -*-
"""T12 可观测性测试：v2 指标覆盖 iteration/tool/replan/终态等。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import (
    AgentDecisionRecord,
    AgentRun,
    AgentRunStatus,
    AgentToolCall,
)
from app.services.agent_observability.operations import (
    observability_overview,
    observability_runs,
)


def _make_runs(app):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="可观测测试",
            mode="hybrid",
            status=AgentRunStatus.COMPLETED.value,
            iteration_count=7,
            replan_count=2,
            tool_call_count=5,
            llm_call_count=9,
            warning_codes=["AGENT_PARTIAL_RESULT"],
        )
        db.session.add(run)
        db.session.flush()
        db.session.add(
            AgentToolCall(
                run_id=run.id,
                tool_name="read_code_slice",
                idempotency_key="k-1",
                logical_call_key=f"{run.id}:node",
                status="succeeded",
                risk_level="safe_read",
                latency_ms=120,
            )
        )
        db.session.add(
            AgentDecisionRecord(
                run_id=run.id,
                plan_version=2,
                supersedes_version=1,
                reason_code="user_direction_extends_plan",
                decision_type="user_direction",
            )
        )
        db.session.commit()
        return run.id


def test_observability_overview_covers_v2_metrics(app):
    run_id = _make_runs(app)
    with app.app_context():
        overview = observability_overview(workspace_id=1, days=7)
        assert "run_counts" in overview
        assert "tools" in overview
        assert "llm" in overview
        assert overview["run_counts"]["total"] >= 1
        assert overview["tools"]["tools"], "工具统计必须有内容"


def test_observability_runs_returns_run_with_v2_fields(app):
    run_id = _make_runs(app)
    with app.app_context():
        items, total = observability_runs(workspace_id=1, page=1, page_size=10)
        assert total >= 1
        target = next(item for item in items if item["id"] == run_id)
        assert target["iteration_count"] == 7
        assert target["replan_count"] == 2
        assert target["tool_call_count"] == 5


def test_observability_runs_supports_status_filter(app):
    _make_runs(app)
    with app.app_context():
        items, total = observability_runs(
            workspace_id=1, page=1, page_size=10, status="completed"
        )
        assert total >= 1
        assert all(item["status"] == "completed" for item in items)


def test_observability_runs_isolated_by_workspace(app):
    _make_runs(app)
    with app.app_context():
        items, total = observability_runs(workspace_id=999, page=1, page_size=10)
        assert total == 0
        assert items == []
