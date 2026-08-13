"""Agent repository/graph/code tool tests: registration, invocation, boundaries."""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentStepExecution,
    AgentToolCall,
)
from app.models.scan_coverage import ProjectSnapshotFile
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.project_security_graph.contracts import GraphBuildBudget
from app.services.project_security_graph.graph_builder import build_project_graph
from app.services.security_agent.tools.code_tools import build_read_code_slice_handler
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)
from app.services.security_agent.tools.graph_tools import (
    build_call_chain_handler,
    build_find_symbol_references_handler,
    build_get_route_map_handler,
    build_search_code_handler,
)
from app.services.security_agent.tools.registry import get_tool_registry
from app.services.security_agent.tools.repository_tools import build_map_repository_handler


def _make_ctx(app, tmp_path, input=None):
    user = User(username="tooluser", email="tool@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="tw", slug="tw-tools")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(workspace_id=workspace.id, name="tp", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    root = tmp_path / "snap"
    root.mkdir(parents=True, exist_ok=True)
    content = (
        "class QaService:\n"
        "    def answer(self):\n"
        "        return 'ok'\n"
    )
    (root / "svc.py").write_text(content, encoding="utf-8")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="sha-tools",
        storage_path=str(root),
        file_count=1,
        total_bytes=len(content),
    )
    db.session.add(snapshot)
    db.session.flush()
    db.session.add(
        ProjectSnapshotFile(
            snapshot_id=snapshot.id,
            file_path="svc.py",
            file_size=len(content),
            extension=".py",
            is_text=True,
            detected_language="python",
        )
    )
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
        node_key="n1",
        node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
        title="map",
        status="running",
    )
    db.session.add(node)
    db.session.flush()
    step = AgentStepExecution(
        run_id=run.id, plan_node_id=node.id, status="running"
    )
    db.session.add(step)
    db.session.flush()
    tool_call = AgentToolCall(
        run_id=run.id,
        step_execution_id=step.id,
        tool_name="map_repository",
        idempotency_key=f"test-{run.id}-map",
    )
    db.session.add(tool_call)
    db.session.flush()
    ctx = ToolExecutionContext(
        run=run,
        plan_node=node,
        step_execution=step,
        tool_call=tool_call,
        workspace_id=workspace.id,
        project_id=project.id,
        snapshot_id=snapshot.id,
        actor_id=user.id,
        trace_id=None,
        input=input or {},
    )
    return ctx, snapshot


def test_graph_tools_registered():
    registry = get_tool_registry()
    for name in (
        "map_repository",
        "get_route_map",
        "get_authentication_map",
        "search_code",
        "find_symbol_references",
        "get_related_files",
        "build_call_chain",
        "read_code_slice",
    ):
        assert registry.has(name), f"{name} 未注册"


def test_map_repository_builds_graph(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    result = build_map_repository_handler()(ctx)
    assert result.status == "succeeded"
    assert result.metrics["node_count"] > 0
    assert result.artifact_refs[0]["artifact_type"] == "security_graph"
    again = build_map_repository_handler()(ctx)
    assert again.status == "succeeded"
    assert again.metrics["status"] == "cached"


def test_map_repository_cancelled_returns_failed(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    from app.models.agent_runtime import AgentRunStatus

    ctx.run.status = AgentRunStatus.CANCELED.value
    db.session.commit()
    result = build_map_repository_handler()(ctx)
    assert result.status == "failed"
    assert result.error_code == "AGENT_TOOL_FAILED"


def test_get_route_map_requires_graph(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    with pytest.raises(ToolExecutionError):
        build_get_route_map_handler()(ctx)


def test_get_route_map_lists_entries(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    build_project_graph(snapshot, budget=GraphBuildBudget())
    ctx.input = {"limit": 20, "offset": 0}
    result = build_get_route_map_handler()(ctx)
    assert result.status == "succeeded"
    assert result.metrics["pagination"]["total"] >= 1


def test_search_code_finds_symbol(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    build_project_graph(snapshot, budget=GraphBuildBudget())
    ctx.input = {"query": "QaService", "limit": 20, "offset": 0}
    result = build_search_code_handler()(ctx)
    assert result.status == "succeeded"
    labels = [node["label"] for node in result.metrics["nodes"]]
    assert "QaService" in labels


def test_search_code_accepts_model_common_field_aliases(app, tmp_path):
    """模型常以 path_pattern/pattern/labels/file_path 调用 search_code，
    必须兼容这些字段名（真实验收 run 65：缺 query 误报必填错误）。"""
    ctx, snapshot = _make_ctx(app, tmp_path)
    build_project_graph(snapshot, budget=GraphBuildBudget())
    handler = build_search_code_handler()

    ctx.input = {"path_pattern": "QaService", "limit": 10}
    result = handler(ctx)
    assert result.status == "succeeded", f"path_pattern 应可用，实际 {result.error_code}"

    ctx.input = {"pattern": "QaService", "limit": 10}
    result = handler(ctx)
    assert result.status == "succeeded", f"pattern 应可用，实际 {result.error_code}"

    ctx.input = {"labels": ["QaService"], "limit": 10}
    result = handler(ctx)
    assert result.status == "succeeded", f"labels 应可用，实际 {result.error_code}"

    ctx.input = {"file_path": "src", "limit": 10}
    result = handler(ctx)
    assert result.status == "succeeded", f"file_path 应可用，实际 {result.error_code}"


def test_search_code_still_rejects_empty_input(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    build_project_graph(snapshot, budget=GraphBuildBudget())
    ctx.input = {"limit": 10}
    with pytest.raises(ToolExecutionError):
        build_search_code_handler()(ctx)


def test_find_symbol_references(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    build_project_graph(snapshot, budget=GraphBuildBudget())
    ctx.input = {"symbol": "QaService", "limit": 20, "offset": 0}
    result = build_find_symbol_references_handler()(ctx)
    assert result.status == "succeeded"
    assert result.metrics["symbol"] == "QaService"


def test_build_call_chain_depth_validation(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    build_project_graph(snapshot, budget=GraphBuildBudget())
    ctx.input = {"symbol": "QaService", "depth": 99}
    with pytest.raises(ToolExecutionError):
        build_call_chain_handler()(ctx)


def test_read_code_slice_returns_restricted_lines(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    ctx.input = {
        "file_path": "svc.py",
        "start_line": 1,
        "end_line": 3,
        "reason": "test evidence",
    }
    result = build_read_code_slice_handler()(ctx)
    assert result.status == "succeeded"
    assert len(result.metrics["lines"]) == 3
    assert result.metrics["lines"][0] == "class QaService:"


def test_read_code_slice_rejects_path_escape(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    ctx.input = {
        "file_path": "../secret.txt",
        "start_line": 1,
        "end_line": 2,
        "reason": "test",
    }
    with pytest.raises(ToolExecutionError) as exc_info:
        build_read_code_slice_handler()(ctx)
    assert exc_info.value.warning_code == "AGENT_CODE_SLICE_FORBIDDEN"


def test_read_code_slice_requires_reason(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    ctx.input = {
        "file_path": "svc.py",
        "start_line": 1,
        "end_line": 2,
        "reason": "",
    }
    with pytest.raises(ToolExecutionError) as exc_info:
        build_read_code_slice_handler()(ctx)
    assert exc_info.value.warning_code == "AGENT_CODE_SLICE_INVALID"


def test_read_code_slice_rejects_too_many_lines(app, tmp_path):
    ctx, snapshot = _make_ctx(app, tmp_path)
    ctx.input = {
        "file_path": "svc.py",
        "start_line": 1,
        "end_line": 999,
        "reason": "test",
    }
    with pytest.raises(ToolExecutionError):
        build_read_code_slice_handler()(ctx)
