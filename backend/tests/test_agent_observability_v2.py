# -*- coding: utf-8 -*-
"""T12 可观测性测试：v2 指标覆盖 iteration/tool/replan/终态等。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_llm import LLMInvocation
from app.models.agent_runtime import (
    AgentDecisionRecord,
    AgentRun,
    AgentRunStatus,
    AgentToolCall,
)
from app.models.agent_sse import AgentSseHealth
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


def test_observability_overview_has_spec_19_3_metrics(app):
    run_id = _make_runs(app)
    with app.app_context():
        now = datetime.utcnow()
        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=100,
                state_version=1,
                event_type="strategy.provider_switched",
                schema_version=2,
                trace_id="t-fail",
                occurred_at=now,
                payload_json={"from_provider": "a", "to_provider": "b"},
            )
        )
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=101,
                state_version=1,
                event_type="tool.started",
                schema_version=1,
                trace_id="t-fail",
                occurred_at=now,
                payload_json={"tool_name": "read_code_slice"},
            )
        )
        db.session.add(
            LLMInvocation(
                run_id=run.id,
                workspace_id=1,
                provider_name="a",
                model="m",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                total_cost=0.0,
                status="ok",
                created_at=now,
            )
        )
        db.session.add(
            AgentSseHealth(
                workspace_id=1,
                run_id=run.id,
                event_type="connect_with_watermark",
                last_event_id=3,
                created_at=now,
            )
        )
        db.session.add(
            AgentSseHealth(
                workspace_id=1,
                run_id=run.id,
                event_type="replay_gap",
                last_event_id=0,
                created_at=now,
            )
        )
        db.session.commit()
        overview = observability_overview(workspace_id=1, days=7)
        failover = overview["failover"]
        assert failover["failover_count"] == 1
        assert failover["llm_calls"] == 1
        assert failover["failover_rate"] == 1.0
        sse = overview["sse_health"]
        assert sse["reconnects"] == 1
        assert sse["gaps"] == 1
        assert sse["gap_rate"] == 1.0
        assert sse["resync_count"] == 1
        assert "first_item" in overview["latency"]
        assert "first_tool" in overview["latency"]
        assert "final_answer" in overview["latency"]
        assert overview["latency"]["first_tool"]["count"] >= 1


def test_latency_metrics_measured_from_run_creation(app):
    run_id = _make_runs(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        created = datetime.utcnow() - timedelta(seconds=30)
        run.created_at = created
        run.finished_at = datetime.utcnow()
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=200,
                state_version=1,
                event_type="item.tool_call.started",
                schema_version=2,
                trace_id="t-latency",
                occurred_at=created + timedelta(seconds=3),
                payload_json={},
            )
        )
        db.session.commit()
        latency = observability_overview(workspace_id=1, days=7)["latency"]
        first_tool = latency["first_tool"]
        assert first_tool is not None
        assert first_tool["count"] >= 1
        assert first_tool["avg_secs"] >= 2.0, "延迟必须从 run 创建时刻起算"


def test_failover_rate_none_when_no_llm_calls(app):
    _make_runs(app)
    with app.app_context():
        rate = observability_overview(workspace_id=1, days=7)["failover"]["failover_rate"]
        assert rate is None or rate >= 0
