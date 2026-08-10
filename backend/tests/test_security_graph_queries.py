"""Security graph query tests: paged neighbors, reverse references, file lookup."""
from __future__ import annotations

from app import db
from app.models.project_security_graph import ProjectSecurityGraphNode
from app.models.scan_coverage import ProjectSnapshotFile
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.project_security_graph import graph_queries
from app.services.project_security_graph.graph_builder import build_project_graph

from test_project_security_graph import _make_snapshot


def _built_snapshot(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    build_project_graph(snapshot)
    return snapshot


def test_entry_nodes_prioritize_routes(app, tmp_path):
    snapshot = _built_snapshot(app, tmp_path)
    nodes, total = graph_queries.entry_nodes(
        snapshot.id, "a4-v1", limit=50, offset=0
    )
    assert total == 3  # 2 file + 1 route
    assert nodes[0].node_type == "route"
    assert nodes[0].metadata_json["rule"] == "/qa"


def test_node_neighbors_paged_outgoing_and_incoming(app, tmp_path):
    snapshot = _built_snapshot(app, tmp_path)
    qa_service = (
        ProjectSecurityGraphNode.query.filter_by(
            snapshot_id=snapshot.id,
            node_key="py:class:app/services/qa_service.py:QaService",
        )
        .first()
    )
    edges, total = graph_queries.node_neighbors(qa_service, limit=1, offset=0)
    assert total == 2  # contains 入边（文件->类）+ contains 出边（类->方法）
    assert len(edges) == 1
    edge = edges[0]
    assert edge.source_node.node_key == "py:file:app/services/qa_service.py"
    assert edge.target_node_id == qa_service.id


def test_incoming_edges_for_label_finds_references(app, tmp_path):
    snapshot = _built_snapshot(app, tmp_path)
    edges, total = graph_queries.incoming_edges_for_label(
        snapshot.id, "a4-v1", "QaService", limit=50, offset=0
    )
    assert total == 1
    assert edges[0].source_node.node_key == "py:file:app/services/qa_service.py"


def test_nodes_for_file(app, tmp_path):
    snapshot = _built_snapshot(app, tmp_path)
    nodes = graph_queries.nodes_for_file(
        snapshot.id, "a4-v1", "app/services/qa_service.py"
    )
    keys = {node.node_key for node in nodes}
    assert "py:file:app/services/qa_service.py" in keys
    assert "py:class:app/services/qa_service.py:QaService" in keys


def test_graph_summary_counts_by_type(app, tmp_path):
    snapshot = _built_snapshot(app, tmp_path)
    summary = graph_queries.graph_summary(snapshot.id, "a4-v1")
    assert summary is not None
    assert summary["node_count"] > 0
    assert summary["edge_count"] > 0
    assert summary["file_count"] == 2
    assert summary["node_types"]["route"] == 1
    assert summary["node_types"]["file"] == 2


def test_graph_summary_none_for_missing_scope(app, tmp_path):
    snapshot = _built_snapshot(app, tmp_path)
    assert graph_queries.graph_summary(snapshot.id, "nope") is None
