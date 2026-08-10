"""Server-side paged graph queries used by API and agent tools."""
from __future__ import annotations

from app import db
from app.models.project_security_graph import (
    ProjectSecurityGraphEdge,
    ProjectSecurityGraphNode,
)


def graph_summary(snapshot_id: int, mapper_version: str) -> dict | None:
    first = (
        ProjectSecurityGraphNode.query.filter_by(
            snapshot_id=snapshot_id, mapper_version=mapper_version
        )
        .first()
    )
    if first is None:
        return None
    from app.services.project_security_graph.cache import graph_stats

    stats = graph_stats(snapshot_id, mapper_version)
    by_type = dict(
        db.session.query(ProjectSecurityGraphNode.node_type, db.func.count())
        .filter_by(snapshot_id=snapshot_id, mapper_version=mapper_version)
        .group_by(ProjectSecurityGraphNode.node_type)
        .all()
    )
    return {
        "snapshot_id": snapshot_id,
        "mapper_version": mapper_version,
        **stats,
        "node_types": {_enum_key(k): int(v) for k, v in by_type.items()},
    }


def _enum_key(value) -> str:
    from enum import Enum

    if isinstance(value, Enum):
        return value.value
    return str(value)


def entry_nodes(
    snapshot_id: int, mapper_version: str, limit: int, offset: int
) -> tuple[list[ProjectSecurityGraphNode], int]:
    """Entry points: route nodes first, then file nodes (paginated)."""
    query = (
        ProjectSecurityGraphNode.query.filter_by(
            snapshot_id=snapshot_id, mapper_version=mapper_version
        )
        .filter(ProjectSecurityGraphNode.node_type.in_(["route", "file"]))
        .order_by(
            db.case(
                (ProjectSecurityGraphNode.node_type == "route", 0),
                else_=1,
            ),
            ProjectSecurityGraphNode.id.asc(),
        )
    )
    total = query.count()
    nodes = query.offset(offset).limit(limit).all()
    return nodes, total


def node_or_none(node_id: int, snapshot_id: int, mapper_version: str) -> ProjectSecurityGraphNode | None:
    return (
        ProjectSecurityGraphNode.query.filter_by(
            id=node_id, snapshot_id=snapshot_id, mapper_version=mapper_version
        )
        .first()
    )


def node_neighbors(
    node: ProjectSecurityGraphNode,
    limit: int,
    offset: int,
    edge_types: list[str] | None = None,
) -> tuple[list[ProjectSecurityGraphEdge], int]:
    """Paged outgoing + incoming edges for one node."""
    query = ProjectSecurityGraphEdge.query.filter(
        db.or_(
            ProjectSecurityGraphEdge.source_node_id == node.id,
            ProjectSecurityGraphEdge.target_node_id == node.id,
        )
    )
    if edge_types:
        query = query.filter(ProjectSecurityGraphEdge.edge_type.in_(edge_types))
    total = query.count()
    edges = (
        query.order_by(ProjectSecurityGraphEdge.id.asc()).offset(offset).limit(limit).all()
    )
    return edges, total


def incoming_edges_for_label(
    snapshot_id: int,
    mapper_version: str,
    label: str,
    limit: int,
    offset: int,
) -> tuple[list[ProjectSecurityGraphEdge], int]:
    """Edges whose target label matches (find_symbol_references support)."""
    target_ids = (
        db.session.query(ProjectSecurityGraphNode.id)
        .filter_by(snapshot_id=snapshot_id, mapper_version=mapper_version)
        .filter(ProjectSecurityGraphNode.label == label)
        .subquery()
    )
    query = ProjectSecurityGraphEdge.query.filter(
        ProjectSecurityGraphEdge.snapshot_id == snapshot_id,
        ProjectSecurityGraphEdge.mapper_version == mapper_version,
        ProjectSecurityGraphEdge.target_node_id.in_(db.session.query(target_ids.c.id)),
    )
    total = query.count()
    edges = (
        query.order_by(ProjectSecurityGraphEdge.id.asc()).offset(offset).limit(limit).all()
    )
    return edges, total


def nodes_for_file(
    snapshot_id: int, mapper_version: str, file_path: str
) -> list[ProjectSecurityGraphNode]:
    return (
        ProjectSecurityGraphNode.query.filter_by(
            snapshot_id=snapshot_id, mapper_version=mapper_version, file_path=file_path
        )
        .order_by(ProjectSecurityGraphNode.start_line.asc())
        .all()
    )
