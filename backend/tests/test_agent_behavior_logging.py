# -*- coding: utf-8 -*-
"""Agent 行为日志测试：滚动文件、时间戳、工具返回信息、安全红线。"""
from __future__ import annotations

import json
from pathlib import Path

from app import db
from app.models.agent_runtime import AgentPlan, AgentPlanNode, AgentPlanNodeStatus, AgentPlanNodeType, AgentStepExecution
from app.services.agent_observability import AgentLogger, configure_agent_logger
from app.services.llm.contracts import LLMStreamChunk
from app.services.security_agent.event_service import EventService
from app.services.security_agent.llm_analysis import AgentLlmAnalysisService

from test_agent_llm_analysis import _FakeStreamProvider, _make_run


def _read_log(app) -> list[dict]:
    path = Path(app.config["AGENT_LOG_FILE"])
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _events_named(app, name):
    return [item for item in _read_log(app) if item.get("event") == name]


def test_configure_agent_logger_creates_file_and_is_idempotent(app):
    with app.app_context():
        configure_agent_logger(app)
        configure_agent_logger(app)

        path = Path(app.config["AGENT_LOG_FILE"])
        assert path.exists()
        logger = AgentLogger()
        logger.run_event("run.created", _make_run())
        rows = _read_log(app)
        assert len(rows) == 1
        assert rows[0]["event"] == "run.created"
        assert rows[0]["ts"], "必须带时间戳"
        assert "T" in rows[0]["ts"] and "Z" in rows[0]["ts"].replace("+00:00", "Z")


def test_tool_event_records_metrics_summary_but_not_file_paths(app):
    with app.app_context():
        run = _make_run()
        logger = AgentLogger()
        logger.tool_event(
            "tool.completed",
            run,
            node_key="baseline_scan",
            tool_name="run_baseline_scan",
            status="succeeded",
            latency_ms=12000,
            step_execution_id=5,
            summary="扫描完成：3 个发现",
            metrics={
                "task_id": 99,
                "findings_count": 3,
                "severity_counts": {"high": 2, "low": 1},
                "total_files": 2,
                "top_findings": [
                    {"file_path": "/srv/secret/app.py", "message": "danger"}
                ],
            },
            trace_id="t-abc",
        )

        row = _events_named(app, "tool.completed")[0]
        assert row["run_id"] == run.id
        assert row["tool_name"] == "run_baseline_scan"
        assert row["node_key"] == "baseline_scan"
        assert row["status"] == "succeeded"
        assert row["latency_ms"] == 12000
        assert row["step_execution_id"] == 5
        assert row["trace_id"] == "t-abc"
        assert row["metrics"]["findings_count"] == 3
        assert row["metrics"]["severity_counts"] == {"high": 2, "low": 1}
        assert "top_findings" not in row["metrics"], "文件路径列表不得进日志"
        assert "/srv/secret/app.py" not in json.dumps(row, ensure_ascii=False)


def test_tool_failure_uses_warning_level(app):
    with app.app_context():
        run = _make_run()
        AgentLogger().tool_event(
            "tool.failed",
            run,
            node_key="baseline_scan",
            tool_name="run_baseline_scan",
            status="failed",
            latency_ms=300,
            summary="扫描失败",
            warning_codes=["AGENT_TOOL_FAILED"],
            error_code="AGENT_TOOL_FAILED",
        )

        row = _events_named(app, "tool.failed")[0]
        assert row["level"] == "WARNING"
        assert row["warning_codes"] == ["AGENT_TOOL_FAILED"]
        assert row["error_code"] == "AGENT_TOOL_FAILED"


def test_llm_event_never_contains_prompt_or_raw_output(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        secret = "sk-abcdefghijklmnopqrstuvwxyz0123"
        provider = _FakeStreamProvider(
            [
                LLMStreamChunk(delta="分析结果文本"),
                LLMStreamChunk(finished=True, usage={"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12}),
            ]
        )
        monkeypatch.setattr(
            "app.services.security_agent.llm_analysis.select_provider",
            lambda *args, **kwargs: provider,
        )

        AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t-sec")

        completed = _events_named(app, "llm.completed")
        assert len(completed) == 1
        row = completed[0]
        assert row["operation"] == "agent_analysis"
        assert row["provider"] == "fake-agent"
        assert row["status"] == "success"
        assert row["total_tokens"] == 12
        assert row["input_digest"], "只允许 digest 进日志"
        text = json.dumps(row, ensure_ascii=False)
        assert "分析结果文本" not in text, "响应原文不得进日志"
        assert secret not in text
        assert "确定性工具证据" not in text, "prompt 不得进日志"


def test_plan_and_budget_logs(app):
    with app.app_context():
        run = _make_run()
        logger = AgentLogger()
        logger.plan_created(
            run,
            planner_source="rule_based_policy",
            plan_version=1,
            node_count=5,
            fallback_reason="未配置 LLM Provider，使用本地策略计划",
            trace_id="t-plan",
        )
        logger.budget_blocked(
            run,
            reached_codes=["AGENT_BUDGET_EXHAUSTED"],
            ratios={"llm_calls": 1.0},
            trace_id="t-budget",
        )

        plan = _events_named(app, "plan.created")[0]
        assert plan["planner_source"] == "rule_based_policy"
        assert plan["node_count"] == 5
        assert "未配置 LLM Provider" in plan["fallback_reason"]

        budget = _events_named(app, "budget.blocked")[0]
        assert budget["level"] == "WARNING"
        assert budget["reached_codes"] == ["AGENT_BUDGET_EXHAUSTED"]


def test_runner_tool_execution_writes_log_with_real_metrics(app, tmp_path):
    """集成：真实 inventory 工具执行后日志包含工具返回信息。"""
    from app.services.security_agent.artifact_service import ArtifactService
    from app.services.security_agent.checkpoint_service import CheckpointService
    from app.services.security_agent.runner import InlinePlanRunner
    from app.services.security_agent.state_machine import AgentStateMachine

    with app.app_context():
        root = tmp_path / "snap"
        root.mkdir(parents=True, exist_ok=True)
        (root / "app.py").write_text("import subprocess\n", encoding="utf-8")
        (root / "readme.md").write_text("# hi\n", encoding="utf-8")

        run = _make_run()
        snapshot = db.session.get(type(run.snapshot), run.snapshot_id)
        snapshot.storage_path = str(root)
        plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
        db.session.add(plan)
        db.session.flush()
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key="inventory",
            node_type=AgentPlanNodeType.INVENTORY.value,
            status=AgentPlanNodeStatus.READY.value,
            title="清点",
            tool_name="inventory_snapshot",
        )
        db.session.add(node)
        db.session.flush()
        step = AgentStepExecution(plan_node_id=node.id, run_id=run.id, attempt_number=1, status="running")
        db.session.add(step)
        db.session.commit()

        runner = InlinePlanRunner(
            state=AgentStateMachine(),
            events=EventService(),
            artifacts=ArtifactService(),
            checkpoints=CheckpointService(),
        )
        runner._run_plan_nodes(run, plan, "t-integration")

        rows = _events_named(app, "tool.completed")
        assert len(rows) == 1
        row = rows[0]
        assert row["tool_name"] == "inventory_snapshot"
        assert row["status"] == "succeeded"
        assert row["metrics"]["file_count"] == 2
        assert row["metrics"]["total_bytes"] > 0
        assert row["node_key"] == "inventory"
        assert row["latency_ms"] is not None
