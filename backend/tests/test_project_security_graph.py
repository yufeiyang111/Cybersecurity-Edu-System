"""Project security graph builder tests: idempotency, budgets, cancellation, isolation."""
from __future__ import annotations

import pytest

from app import db
from app.models.project_security_graph import (
    ProjectSecurityGraphEdge,
    ProjectSecurityGraphNode,
)
from app.models.scan_coverage import ProjectSnapshotFile
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.project_security_graph.contracts import GraphBuildBudget
from app.services.project_security_graph.graph_builder import build_project_graph


def _make_snapshot(app, tmp_path, *, project_name="gproj", extra_files=None):
    user = User(username="graphuser", email="graph@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="gw", slug="gw-graph")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(
        workspace_id=workspace.id, name=project_name, created_by=user.id
    )
    db.session.add(project)
    db.session.flush()
    root = tmp_path / "snap"
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "app/routes/qa.py": (
            "from app.services.qa_service import QaService\n"
            "bp = None\n"
            "@bp.route('/qa', methods=['POST'])\n"
            "def ask():\n"
            "    svc = QaService()\n"
            "    return svc.answer()\n"
        ),
        "app/services/qa_service.py": (
            "class QaService:\n"
            "    def answer(self):\n"
            "        return 'ok'\n"
        ),
    }
    if extra_files:
        files.update(extra_files)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="sha-graph",
        storage_path=str(root),
        file_count=len(files),
        total_bytes=1,
    )
    db.session.add(snapshot)
    db.session.flush()
    for rel, content in files.items():
        db.session.add(
            ProjectSnapshotFile(
                snapshot_id=snapshot.id,
                file_path=rel,
                file_size=len(content.encode("utf-8")),
                extension=".py",
                is_text=True,
                detected_language="python",
            )
        )
    db.session.commit()
    return snapshot


def test_build_graph_creates_nodes_and_edges(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    result = build_project_graph(snapshot)
    assert result.status == "built"
    assert result.node_count > 0
    assert result.edge_count > 0
    assert result.file_count == 2
    nodes = ProjectSecurityGraphNode.query.filter_by(snapshot_id=snapshot.id).all()
    keys = {node.node_key for node in nodes}
    assert "py:file:app/routes/qa.py" in keys
    assert "py:class:app/services/qa_service.py:QaService" in keys
    route_keys = {key for key in keys if ":route:" in key}
    assert route_keys, "应生成路由节点"


def test_build_graph_imports_edge_resolves_cross_file(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    build_project_graph(snapshot)
    import_edges = ProjectSecurityGraphEdge.query.filter_by(
        snapshot_id=snapshot.id, edge_type="imports"
    ).all()
    assert len(import_edges) == 1
    edge = import_edges[0]
    assert edge.confidence == "exact"
    assert edge.extractor == "python_ast"
    assert edge.source_node.node_key == "py:file:app/routes/qa.py"
    assert edge.target_node.node_key == "py:file:app/services/qa_service.py"


def test_build_graph_is_idempotent(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    first = build_project_graph(snapshot)
    second = build_project_graph(snapshot)
    assert first.status == "built"
    assert second.status == "cached"
    node_count = ProjectSecurityGraphNode.query.filter_by(
        snapshot_id=snapshot.id
    ).count()
    edge_count = ProjectSecurityGraphEdge.query.filter_by(
        snapshot_id=snapshot.id
    ).count()
    assert node_count == first.node_count
    assert edge_count == first.edge_count


def test_build_graph_respects_node_budget(app, tmp_path):
    snapshot = _make_snapshot(
        app,
        tmp_path,
        extra_files={
            f"app/modules/mod{i}.py": f"def fn{i}():\n    return {i}\n"
            for i in range(10)
        },
    )
    budget = GraphBuildBudget(max_nodes=5)
    result = build_project_graph(snapshot, budget=budget)
    assert result.status == "partial"
    assert result.node_count <= 5


def test_build_graph_cancellation_returns_cancelled(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    result = build_project_graph(snapshot, is_cancelled=lambda: True)
    assert result.status == "cancelled"
    assert ProjectSecurityGraphNode.query.filter_by(snapshot_id=snapshot.id).count() == 0


def test_build_graph_skips_outside_files_and_missing_files(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    root = tmp_path / "snap"
    (root / "escape.py").write_text("x = 1\n", encoding="utf-8")
    db.session.add(
        ProjectSnapshotFile(
            snapshot_id=snapshot.id,
            file_path="../../../etc/passwd",
            file_size=1,
            extension=".py",
            is_text=True,
            detected_language="python",
        )
    )
    db.session.commit()
    result = build_project_graph(snapshot)
    assert result.status == "built"
    keys = {
        node.node_key
        for node in ProjectSecurityGraphNode.query.filter_by(snapshot_id=snapshot.id).all()
    }
    assert not any("etc/passwd" in key for key in keys)


def test_build_graph_isolates_mapper_versions(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    build_project_graph(snapshot, mapper_version="a4-v1")
    build_project_graph(snapshot, mapper_version="a4-v2")
    v1_count = ProjectSecurityGraphNode.query.filter_by(
        snapshot_id=snapshot.id, mapper_version="a4-v1"
    ).count()
    v2_count = ProjectSecurityGraphNode.query.filter_by(
        snapshot_id=snapshot.id, mapper_version="a4-v2"
    ).count()
    assert v1_count > 0
    assert v2_count > 0
    assert v1_count == v2_count


def test_build_graph_failed_without_storage(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    snapshot.storage_path = None
    db.session.commit()
    result = build_project_graph(snapshot)
    assert result.status == "failed"
    assert result.error_code == "AGENT_GRAPH_NO_STORAGE"
