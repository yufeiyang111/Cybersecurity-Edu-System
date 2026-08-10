"""Graph build orchestration: idempotent, budgeted, cancellable."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from app import db
from app.models.project_security_graph import (
    ProjectSecurityGraphEdge,
    ProjectSecurityGraphNode,
)
from app.models.scan_coverage import ProjectSnapshotFile
from app.models.security import ProjectSnapshot
from app.services.project_security_graph.cache import graph_stats, has_graph
from app.services.project_security_graph.contracts import (
    DEFAULT_MAPPER_VERSION,
    EdgeDraft,
    GraphBuildBudget,
    GraphBuildResult,
    NodeDraft,
    _confidence_value,
    _edge_type_value,
    _node_type_value,
    module_to_path,
)
from app.services.project_security_graph.file_mapper import map_file

CancellationCheck = Callable[[], bool]


def _resolve_cross_file_edges(
    nodes: list[NodeDraft],
) -> list[EdgeDraft]:
    """Best-effort cross-file imports: module name -> mapped file path.

    Only exact file hits produce an edge; unresolved imports are skipped so the
    graph never fabricates relations.
    """
    resolved: list[EdgeDraft] = []
    file_key_by_path: dict[str, str] = {}
    for draft in nodes:
        if _node_type_value(draft.node_type) == "file" and draft.file_path:
            file_key_by_path[draft.file_path] = draft.node_key
    for draft in nodes:
        if not draft.file_path or draft.file_path not in file_key_by_path:
            continue
        source_key = file_key_by_path[draft.file_path]
        for imp in draft.metadata.get("imports", []):
            if imp.get("is_relative") or not imp.get("module"):
                continue
            for candidate in module_to_path(imp["module"]):
                if candidate in file_key_by_path:
                    resolved.append(
                        EdgeDraft(
                            source_key=source_key,
                            target_key=file_key_by_path[candidate],
                            edge_type="imports",
                            extractor="python_ast",
                            confidence="exact",
                        )
                    )
                    break
    return resolved


def _persist_graph(
    snapshot_id: int,
    mapper_version: str,
    nodes: list[NodeDraft],
    edges: list[EdgeDraft],
) -> None:
    node_rows: list[ProjectSecurityGraphNode] = []
    key_to_id: dict[str, int] = {}
    seen_keys: set[str] = set()
    for draft in nodes:
        if draft.node_key in seen_keys:
            continue
        seen_keys.add(draft.node_key)
        row = ProjectSecurityGraphNode(
            snapshot_id=snapshot_id,
            mapper_version=mapper_version,
            node_key=draft.node_key,
            node_type=_node_type_value(draft.node_type),
            label=draft.label,
            file_path=draft.file_path,
            start_line=draft.start_line,
            end_line=draft.end_line,
            language=draft.language,
            metadata_json=draft.metadata or None,
        )
        node_rows.append(row)
        key_to_id[draft.node_key] = len(node_rows) - 1
    db.session.add_all(node_rows)
    db.session.flush()

    edge_rows: list[ProjectSecurityGraphEdge] = []
    seen_edges: set[tuple[int, int, str, str]] = set()
    for draft in edges:
        source_id = key_to_id.get(draft.source_key)
        target_id = key_to_id.get(draft.target_key)
        if source_id is None or target_id is None or source_id == target_id:
            continue
        edge_type = _edge_type_value(draft.edge_type)
        confidence = _confidence_value(draft.confidence)
        dedupe_key = (source_id, target_id, edge_type, confidence)
        if dedupe_key in seen_edges:
            continue
        seen_edges.add(dedupe_key)
        edge_rows.append(
            ProjectSecurityGraphEdge(
                snapshot_id=snapshot_id,
                mapper_version=mapper_version,
                source_node_id=node_rows[source_id].id,
                target_node_id=node_rows[target_id].id,
                edge_type=edge_type,
                extractor=draft.extractor,
                confidence=confidence,
                quality=draft.quality,
            )
        )
    db.session.add_all(edge_rows)


def build_project_graph(
    snapshot: ProjectSnapshot,
    mapper_version: str = DEFAULT_MAPPER_VERSION,
    budget: GraphBuildBudget | None = None,
    is_cancelled: CancellationCheck | None = None,
) -> GraphBuildResult:
    """Build (or return cached) project security graph for one snapshot.

    Idempotent: a previously built scope (snapshot_id + mapper_version) is
    returned as ``cached`` without touching the database.
    """
    budget = budget or GraphBuildBudget()
    cancelled = is_cancelled or (lambda: False)
    if has_graph(snapshot.id, mapper_version):
        stats = graph_stats(snapshot.id, mapper_version)
        return GraphBuildResult(
            status="cached",
            mapper_version=mapper_version,
            node_count=stats["node_count"],
            edge_count=stats["edge_count"],
            file_count=stats["file_count"],
        )

    if not snapshot.storage_path:
        return GraphBuildResult(
            status="failed",
            mapper_version=mapper_version,
            error_code="AGENT_GRAPH_NO_STORAGE",
            message="快照存储路径缺失，无法建图",
        )
    root = Path(snapshot.storage_path).resolve()
    if not root.is_dir():
        return GraphBuildResult(
            status="failed",
            mapper_version=mapper_version,
            error_code="AGENT_GRAPH_NO_STORAGE",
            message="快照存储目录不存在或不可读",
        )

    files = (
        ProjectSnapshotFile.query.filter_by(snapshot_id=snapshot.id, is_text=True)
        .order_by(ProjectSnapshotFile.file_path.asc())
        .all()
    )
    if not files:
        return GraphBuildResult(
            status="failed",
            mapper_version=mapper_version,
            error_code="AGENT_GRAPH_NO_FILES",
            message="快照没有可解析的文本文件",
        )

    all_nodes: list[NodeDraft] = []
    all_edges: list[EdgeDraft] = []
    processed_files = 0
    status = "built"
    message = ""

    for entry in files:
        if cancelled():
            status = "cancelled"
            message = "建图任务已取消"
            break
        if len(all_nodes) >= budget.max_nodes:
            status = "partial"
            message = f"达到节点预算 {budget.max_nodes}，已提前停止"
            break
        target = (root / entry.file_path).resolve()
        if not target.is_relative_to(root):
            continue
        if not target.is_file():
            continue
        if target.stat().st_size > budget.max_file_bytes:
            continue
        try:
            source = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        mapped = map_file(entry.file_path, entry.extension, source, budget)
        if mapped is None:
            continue
        file_nodes, file_edges = mapped
        if len(all_nodes) + len(file_nodes) > budget.max_nodes:
            status = "partial"
            message = f"达到节点预算 {budget.max_nodes}，已提前停止"
            file_nodes = file_nodes[: budget.max_nodes - len(all_nodes)]
        if len(all_edges) + len(file_edges) > budget.max_edges:
            status = "partial"
            message = f"达到边预算 {budget.max_edges}，已提前停止"
            file_edges = file_edges[: budget.max_edges - len(all_edges)]
        all_nodes.extend(file_nodes)
        all_edges.extend(file_edges)
        processed_files += 1

    if not cancelled() and status == "built":
        all_edges.extend(_resolve_cross_file_edges(all_nodes))
        if len(all_edges) > budget.max_edges:
            all_edges = all_edges[: budget.max_edges]
            status = "partial"
            message = f"达到边预算 {budget.max_edges}，已提前停止"

    if status == "cancelled":
        return GraphBuildResult(
            status="cancelled",
            mapper_version=mapper_version,
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            file_count=processed_files,
            error_code="AGENT_GRAPH_CANCELLED",
            message=message,
        )

    if not all_nodes:
        return GraphBuildResult(
            status="failed",
            mapper_version=mapper_version,
            error_code="AGENT_GRAPH_EMPTY",
            message="没有生成任何图节点",
        )

    _persist_graph(snapshot.id, mapper_version, all_nodes, all_edges)
    db.session.commit()
    return GraphBuildResult(
        status=status,
        mapper_version=mapper_version,
        node_count=len(all_nodes),
        edge_count=len(all_edges),
        file_count=processed_files,
        error_code="AGENT_GRAPH_PARTIAL" if status == "partial" else None,
        message=message,
    )
