# -*- coding: utf-8 -*-
"""A5 服务层测试：证据评估、策略目录、重规划与限制。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import (
    AgentDecisionRecord,
    AgentPlan,
    AgentPlanEdge,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
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
from app.services.security_agent.decision_records import DecisionRecords
from app.services.security_agent.evidence_evaluator import EvidenceEvaluator
from app.services.security_agent.event_service import EventService
from app.services.security_agent.replanner import Replanner
from app.services.security_agent.strategy_catalog import (
    REASON_HIGH_FINDINGS,
    REASON_USER_DIRECTION,
    evaluate_evidence,
    normalize_user_direction_nodes,
    related_review_nodes,
)


def _make_run(app, *, status=AgentRunStatus.EXECUTING_TOOLS.value, planner="rule_based_policy"):
    user = User(username="ev", email="ev@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="w", slug="w-ev")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(workspace_id=workspace.id, name="p", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="c1",
        storage_path="x",
        file_count=1,
        total_bytes=10,
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
        status=status,
        planner_source=planner,
    )
    db.session.add(run)
    db.session.flush()
    return run


def _make_plan(run, *, nodes=("inventory", "baseline_scan")):
    plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
    db.session.add(plan)
    db.session.flush()
    for key in nodes:
        db.session.add(
            AgentPlanNode(
                plan_id=plan.id,
                node_key=key,
                node_type=AgentPlanNodeType.BASELINE_SCAN.value,
                status=AgentPlanNodeStatus.SUCCEEDED.value,
                title=key,
                tool_name="inventory_snapshot",
            )
        )
    db.session.flush()
    return plan


def _seed_findings(run, *, high=0, total=0):
    task = ScanTask(
        snapshot_id=run.snapshot_id,
        status="completed",
    )
    db.session.add(task)
    db.session.flush()
    severities = ["high"] * high + ["low"] * max(0, total - high)
    for index, severity in enumerate(severities):
        db.session.add(
            SecurityFinding(
                task_id=task.id,
                fingerprint=f"fp-{index}",
                rule_id=f"RULE-{index}",
                category="sast",
                severity=severity,
                file_path=f"app{index}.py",
                start_line=1,
                message="t",
            )
        )
    db.session.flush()
    return task


# --------------------------------------------------------------- evidence


def test_evidence_evaluator_empty(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        evidence = EvidenceEvaluator().evaluate(run, plan)
        assert evidence.total_findings == 0
        assert evidence.high_severity_count == 0
        assert evidence.high_finding_files == ()
        assert evidence.plan_completed is True


def test_evidence_evaluator_high_findings(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        _seed_findings(run, high=2, total=3)
        evidence = EvidenceEvaluator().evaluate(run, plan)
        assert evidence.total_findings == 3
        assert evidence.high_severity_count == 2
        assert evidence.high_finding_files == ("app0.py", "app1.py")


def test_evidence_evaluator_failed_nodes(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        plan.nodes[1].status = AgentPlanNodeStatus.FAILED.value
        db.session.commit()
        evidence = EvidenceEvaluator().evaluate(run, plan)
        assert evidence.failed_node_keys == ("baseline_scan",)
        assert evidence.plan_completed is False


# ------------------------------------------------------------ strategy catalog


def test_strategy_no_replan_without_high_findings(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        _seed_findings(run, high=0, total=1)
        evidence = EvidenceEvaluator().evaluate(run, plan)
        decision = evaluate_evidence(evidence, {n.node_key for n in plan.nodes})
        assert decision.should_replan is False


def test_strategy_replans_on_high_findings(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        _seed_findings(run, high=1, total=1)
        evidence = EvidenceEvaluator().evaluate(run, plan)
        decision = evaluate_evidence(evidence, {n.node_key for n in plan.nodes})
        assert decision.should_replan is True
        assert decision.reason_code == REASON_HIGH_FINDINGS
        keys = [spec.key for spec in decision.node_specs]
        assert "related_graph_build" in keys
        assert "related_high_finding_files" in keys
        first = decision.node_specs[0]
        assert first.tool_name == "map_repository"


def test_strategy_no_duplicate_related_nodes(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        _seed_findings(run, high=1, total=1)
        evidence = EvidenceEvaluator().evaluate(run, plan)
        decision = evaluate_evidence(evidence, {"related_graph_build", "baseline_scan"})
        assert decision.should_replan is False


def test_user_direction_nodes_mapping():
    auth = normalize_user_direction_nodes("重点检查鉴权和登录逻辑")
    assert [spec.key for spec in auth] == ["direction_graph_build", "direction_focused_review"]
    assert auth[1].tool_name == "get_authentication_map"
    sql = normalize_user_direction_nodes("看看 SQL 注入")
    assert sql[1].tool_name == "search_code"
    assert sql[1].input == {"query": "execute"}
    default = normalize_user_direction_nodes("随便看看")
    assert default[1].tool_name == "get_route_map"


# ----------------------------------------------------------------- replanner


def test_replanner_creates_version_with_new_nodes(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run, nodes=("inventory", "baseline_scan"))
        specs = normalize_user_direction_nodes("检查文件上传")
        events = EventService()
        new_plan = Replanner(events).create_version(
            run,
            plan,
            reason_code=REASON_USER_DIRECTION,
            decision_type="user_direction",
            node_specs=specs,
            decision_summary="用户追加方向",
        )
        assert new_plan.plan_version == 2
        assert run.plan_version == 2
        assert run.replan_count == 1
        keys = {node.node_key for node in new_plan.nodes}
        assert {"inventory", "baseline_scan", "direction_graph_build", "direction_focused_review"} <= keys
        new_node = next(n for n in new_plan.nodes if n.node_key == "direction_graph_build")
        assert new_node.status == AgentPlanNodeStatus.READY.value
        review_node = next(n for n in new_plan.nodes if n.node_key == "direction_focused_review")
        assert review_node.status == AgentPlanNodeStatus.PENDING.value
        assert review_node.input_json == {"query": "upload"}
        assert review_node.depends_on_json == ["direction_graph_build"]
        assert len(new_plan.edges) >= 1
        record = (
            AgentDecisionRecord.query.filter_by(run_id=run.id)
            .order_by(AgentDecisionRecord.id.desc())
            .first()
        )
        assert record.plan_version == 2
        assert record.supersedes_version == 1
        assert record.reason_code == REASON_USER_DIRECTION
        assert record.decision_type == "user_direction"


def test_replanner_skips_duplicate_node_keys(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        specs = normalize_user_direction_nodes("检查文件上传")
        new_plan = Replanner(EventService()).create_version(
            run,
            plan,
            reason_code=REASON_USER_DIRECTION,
            decision_type="user_direction",
            node_specs=specs,
        )
        keys = [node.node_key for node in new_plan.nodes]
        assert len(keys) == len(set(keys)), "同计划内不允许重复 node_key"


def test_replanner_limit_max_replans(app):
    with app.app_context():
        run = _make_run(app)
        run.replan_count = 2
        plan = _make_plan(run)
        app.config["AGENT_MAX_REPLANS"] = 2
        events = EventService()
        result = Replanner(events).create_version(
            run,
            plan,
            reason_code=REASON_HIGH_FINDINGS,
            decision_type="auto",
            node_specs=related_review_nodes(("app.py",)),
        )
        assert result is None
        warnings = [e.payload_json.get("warning_codes", []) for e in events.tail(run.id)]
        assert any("AGENT_REPLAN_LIMIT_REACHED" in codes for codes in warnings)


def test_replanner_limit_same_route(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run)
        DecisionRecords(EventService()).record(
            run,
            plan_version=1,
            supersedes_version=None,
            reason_code=REASON_HIGH_FINDINGS,
            decision_type="auto",
        )
        DecisionRecords(EventService()).record(
            run,
            plan_version=2,
            supersedes_version=1,
            reason_code=REASON_HIGH_FINDINGS,
            decision_type="auto",
        )
        app.config["AGENT_MAX_SAME_FAILURE_ROUTE"] = 2
        result = Replanner(EventService()).create_version(
            run,
            plan,
            reason_code=REASON_HIGH_FINDINGS,
            decision_type="auto",
            node_specs=related_review_nodes(("app.py",)),
        )
        assert result is None


def test_replanner_preserves_copied_node_states(app):
    with app.app_context():
        run = _make_run(app)
        plan = _make_plan(run, nodes=("inventory", "baseline_scan"))
        plan.nodes[1].status = AgentPlanNodeStatus.FAILED.value
        db.session.commit()
        new_plan = Replanner(EventService()).create_version(
            run,
            plan,
            reason_code=REASON_USER_DIRECTION,
            decision_type="user_direction",
            node_specs=normalize_user_direction_nodes("检查 admin 路由"),
        )
        copied = {node.node_key: node.status for node in new_plan.nodes}
        assert copied["baseline_scan"] == AgentPlanNodeStatus.FAILED.value
        assert copied["inventory"] == AgentPlanNodeStatus.SUCCEEDED.value
