"""Agent scan tool tests: baseline scan really invokes the scanner pipeline."""
from __future__ import annotations

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentStepExecution,
)
from app.models.security import (
    ProjectSnapshot,
    ScanTask,
    SecurityFinding,
    SecurityProject,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User
from app.services.scan_exclusion import GitignoreMatcher
from app.services.security_agent.event_service import EventService
from app.services.security_agent.tools.coverage_tools import build_coverage_handler
from app.services.security_agent.tools.contracts import ToolExecutionContext
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import get_tool_registry
from app.services.security_agent.tools.risk_tools import build_rank_findings_handler
from app.services.security_agent.tools.scan_tools import build_baseline_scan_handler


def _make_run_and_node(app, tmp_path):
    user = User(username="scantool", email="scantool@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="w", slug="w-scan")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(workspace_id=workspace.id, name="scan", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    root = tmp_path / "snap"
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text(
        "import subprocess\n"
        "def run(cmd):\n"
        "    return subprocess.run(cmd, shell=True)\n"
        "API_KEY = 'sk-scan-tool-secret-12345'\n",
        encoding="utf-8",
    )
    (root / "readme.md").write_text("# hi\n", encoding="utf-8")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="c",
        storage_path=str(root),
        file_count=2,
        total_bytes=100,
    )
    db.session.add(snapshot)
    db.session.flush()
    run = AgentRun(
        workspace_id=workspace.id,
        project_id=project.id,
        snapshot_id=snapshot.id,
        created_by=user.id,
        goal_text="g",
        mode=AgentRunMode.BASELINE.value,
        status=AgentRunStatus.EXECUTING_TOOLS.value,
    )
    db.session.add(run)
    db.session.flush()
    plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
    db.session.add(plan)
    db.session.flush()
    node = AgentPlanNode(
        plan_id=plan.id,
        node_key="baseline_scan",
        node_type=AgentPlanNodeType.BASELINE_SCAN.value,
        status=AgentPlanNodeStatus.READY.value,
        title="t",
        tool_name="run_baseline_scan",
    )
    db.session.add(node)
    db.session.flush()
    step = AgentStepExecution(plan_node_id=node.id, run_id=run.id, attempt_number=1, status="running")
    db.session.add(step)
    db.session.commit()
    return run, node, step


def _ctx(app, run, node, step):
    executor = ToolExecutor(get_tool_registry(), EventService())
    return executor.execute(run, node, step, actor_id=run.created_by, trace_id="t")


def test_baseline_scan_tool_runs_real_scanners(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        result = _ctx(app, run, node, step)
        assert result.status == "succeeded"
        assert result.metrics["task_id"] > 0
        assert result.metrics["findings_count"] >= 2, "必须真实扫出 SAST + Secret 发现"
        assert result.metrics["severity_counts"]["high"] >= 2
        assert result.metrics["languages"] == ["python"]
        paths = {item["file_path"] for item in result.metrics["top_findings"]}
        assert "app.py" in paths
        task_id = result.metrics["task_id"]
        persisted = SecurityFinding.query.filter_by(task_id=task_id).all()
        assert len(persisted) >= 2
        for finding in persisted:
            assert finding.file_path in {"app.py", "readme.md"}


def test_coverage_tool_reports_scanned_files(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        baseline = _ctx(app, run, node, step)
        task_id = baseline.metrics["task_id"]

        coverage_node = AgentPlanNode(
            plan_id=node.plan_id,
            node_key="coverage_analysis",
            node_type="coverage_analysis",
            status="ready",
            title="c",
            tool_name="get_scan_coverage",
        )
        db.session.add(coverage_node)
        db.session.flush()
        coverage_step = AgentStepExecution(
            plan_node_id=coverage_node.id, run_id=run.id, attempt_number=1, status="running"
        )
        db.session.add(coverage_step)
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        result = executor.execute(run, coverage_node, coverage_step, actor_id=run.created_by, trace_id="t")
        assert result.status == "succeeded"
        assert result.metrics["total_files"] == 2
        assert result.metrics["scanned_with_findings"] >= 1
        assert result.metrics["scanned_no_finding"] >= 1
        assert result.metrics["specialized_sast"] == 1


def test_rank_findings_tool_sorts_by_risk(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        _ctx(app, run, node, step)

        rank_node = AgentPlanNode(
            plan_id=node.plan_id,
            node_key="risk_ranking",
            node_type="risk_ranking",
            status="ready",
            title="r",
            tool_name="rank_findings",
        )
        db.session.add(rank_node)
        db.session.flush()
        rank_step = AgentStepExecution(plan_node_id=rank_node.id, run_id=run.id, attempt_number=1, status="running")
        db.session.add(rank_step)
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        result = executor.execute(run, rank_node, rank_step, actor_id=run.created_by, trace_id="t")
        assert result.status == "succeeded"
        assert result.metrics["ranked_count"] >= 2
        scores = [item["risk_score"] for item in result.metrics["top_ranked"]]
        assert scores == sorted(scores, reverse=True), "必须按风险分降序"


def test_run_scanner_tool_directed_python_only(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        scanner_node = AgentPlanNode(
            plan_id=node.plan_id,
            node_key="directed_scan",
            node_type="baseline_scan",
            status="ready",
            title="d",
            tool_name="run_scanner",
        )
        db.session.add(scanner_node)
        db.session.flush()
        scanner_step = AgentStepExecution(
            plan_node_id=scanner_node.id, run_id=run.id, attempt_number=1, status="running"
        )
        db.session.add(scanner_step)
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        result = executor.execute(
            run,
            scanner_node,
            scanner_step,
            actor_id=run.created_by,
            trace_id="t",
            input_payload={"scanner_names": ["python-baseline"]},
        )
        assert result.status == "succeeded"
        assert result.metrics["scanner_names"] == ["python-baseline"]
        assert result.metrics["task_id"] > 0
        assert result.metrics["findings_count"] >= 1
        task_id = result.metrics["task_id"]
        task = ScanTask.query.get(task_id)
        assert task.summary_json["secret_findings_count"] == 0, "定向 python 不应执行 universal secret"
        persisted = SecurityFinding.query.filter_by(task_id=task_id).all()
        assert all(f.file_path == "app.py" for f in persisted), "定向 python 只扫描语言文件"


def test_run_scanner_tool_directed_secret(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        scanner_node = AgentPlanNode(
            plan_id=node.plan_id,
            node_key="secret_scan",
            node_type="baseline_scan",
            status="ready",
            title="s",
            tool_name="run_scanner",
        )
        db.session.add(scanner_node)
        db.session.flush()
        scanner_step = AgentStepExecution(
            plan_node_id=scanner_node.id, run_id=run.id, attempt_number=1, status="running"
        )
        db.session.add(scanner_step)
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        result = executor.execute(
            run,
            scanner_node,
            scanner_step,
            actor_id=run.created_by,
            trace_id="t",
            input_payload={"scanner_names": ["universal_secret"]},
        )
        assert result.status == "succeeded"
        assert result.metrics["findings_count"] >= 1
        task_id = result.metrics["task_id"]
        task = ScanTask.query.get(task_id)
        assert task.summary_json["secret_findings_count"] >= 1, "定向 universal_secret 应产出 secret 发现"
        persisted = SecurityFinding.query.filter_by(task_id=task_id).all()
        assert all(f.category == "secret" for f in persisted)


def test_run_scanner_tool_rejects_unknown_scanner(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        scanner_node = AgentPlanNode(
            plan_id=node.plan_id,
            node_key="bad_scan",
            node_type="baseline_scan",
            status="ready",
            title="b",
            tool_name="run_scanner",
        )
        db.session.add(scanner_node)
        db.session.flush()
        scanner_step = AgentStepExecution(
            plan_node_id=scanner_node.id, run_id=run.id, attempt_number=1, status="running"
        )
        db.session.add(scanner_step)
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        result = executor.execute(
            run,
            scanner_node,
            scanner_step,
            actor_id=run.created_by,
            trace_id="t",
            input_payload={"scanner_names": ["not-a-scanner"]},
        )
        assert result.status == "failed"
        assert "not-a-scanner" in result.summary


def test_run_scanner_tool_rejects_empty_names(app, tmp_path):
    with app.app_context():
        run, node, step = _make_run_and_node(app, tmp_path)
        scanner_node = AgentPlanNode(
            plan_id=node.plan_id,
            node_key="empty_scan",
            node_type="baseline_scan",
            status="ready",
            title="e",
            tool_name="run_scanner",
        )
        db.session.add(scanner_node)
        db.session.flush()
        scanner_step = AgentStepExecution(
            plan_node_id=scanner_node.id, run_id=run.id, attempt_number=1, status="running"
        )
        db.session.add(scanner_step)
        db.session.commit()
        executor = ToolExecutor(get_tool_registry(), EventService())
        result = executor.execute(
            run,
            scanner_node,
            scanner_step,
            actor_id=run.created_by,
            trace_id="t",
            input_payload={"scanner_names": []},
        )
        assert result.status == "failed"
        assert "scanner_names" in result.summary