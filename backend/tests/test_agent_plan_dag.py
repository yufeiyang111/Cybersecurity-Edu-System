"""Agent plan DAG tests: five-node baseline DAG structure and execution order."""
from __future__ import annotations

from app import db
from app.models.agent_runtime import (
    AgentPlanEdge,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentRun,
    AgentRunMode,
)
from app.models.security import ProjectSnapshot, SecurityProject
from app.models.user import User
from app.services.security_agent.runner import InlinePlanRunner
from app.services.security_agent.state_machine import AgentStateMachine
from app.services.workspaces import get_or_create_personal_workspace

EXPECTED_ORDER = [
    "inventory",
    "baseline_scan",
    "coverage_analysis",
    "risk_ranking",
    "report",
]


def _make_run_with_plan(app, tmp_path) -> tuple[AgentRun, list[AgentPlanNode], list[AgentPlanEdge]]:
    user = User(username="dag", email="dag@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = get_or_create_personal_workspace(user.id)
    project = SecurityProject(workspace_id=workspace.id, name="dag", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    root = tmp_path / "snap"
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.py").write_text("x=1", encoding="utf-8")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="c",
        storage_path=str(root),
        file_count=1,
        total_bytes=3,
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
        status="queued",
    )
    db.session.add(run)
    db.session.commit()
    from app.services.security_agent.event_service import EventService

    runner = InlinePlanRunner(
        state=AgentStateMachine(),
        events=EventService(),
        artifacts=__import__(
            "app.services.security_agent.artifact_service", fromlist=["ArtifactService"]
        ).ArtifactService(),
        checkpoints=__import__(
            "app.services.security_agent.checkpoint_service", fromlist=["CheckpointService"]
        ).CheckpointService(),
    )
    plan = runner._build_plan(run, "trace")
    nodes = sorted(plan.nodes, key=lambda node: node.id)
    edges = plan.edges
    return run, nodes, edges


def test_plan_dag_has_five_nodes_in_order(app, tmp_path):
    with app.app_context():
        run, nodes, edges = _make_run_with_plan(app, tmp_path)
        assert [node.node_key for node in nodes] == EXPECTED_ORDER
        assert nodes[0].status == "ready"
        assert all(node.status == "pending" for node in nodes[1:])


def test_plan_dag_edges_are_dependency_consistent(app, tmp_path):
    with app.app_context():
        run, nodes, edges = _make_run_with_plan(app, tmp_path)
        by_key = {node.node_key: node for node in nodes}
        for edge in edges:
            assert edge.from_node in by_key
            assert edge.to_node in by_key
            assert edge.to_node != edge.from_node
        deps = {node.node_key: (node.depends_on_json or []) for node in nodes}
        assert deps["baseline_scan"] == ["inventory"]
        assert deps["coverage_analysis"] == ["baseline_scan"]
        assert deps["risk_ranking"] == ["baseline_scan"]
        assert deps["report"] == ["coverage_analysis", "risk_ranking"]


def test_plan_dag_is_acyclic(app, tmp_path):
    with app.app_context():
        run, nodes, edges = _make_run_with_plan(app, tmp_path)
        indegree = {node.node_key: 0 for node in nodes}
        adjacency = {node.node_key: [] for node in nodes}
        for edge in edges:
            adjacency[edge.from_node].append(edge.to_node)
            indegree[edge.to_node] += 1
        queue = [key for key, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            current = queue.pop()
            visited += 1
            for neighbor in adjacency[current]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)
        assert visited == len(nodes), "计划 DAG 必须无环"
