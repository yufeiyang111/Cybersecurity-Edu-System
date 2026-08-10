"""Graph cache helpers: idempotency check and stats for a build scope."""
from __future__ import annotations

from app import db
from app.models.project_security_graph import (
    ProjectSecurityGraphEdge,
    ProjectSecurityGraphNode,
)


def has_graph(snapshot_id: int, mapper_version: str) -> bool:
    return (
        db.session.query(ProjectSecurityGraphNode.id)
        .filter_by(snapshot_id=snapshot_id, mapper_version=mapper_version)
        .first()
        is not None
    )


def graph_stats(snapshot_id: int, mapper_version: str) -> dict:
    node_count = (
        db.session.query(ProjectSecurityGraphNode.id)
        .filter_by(snapshot_id=snapshot_id, mapper_version=mapper_version)
        .count()
    )
    edge_count = (
        db.session.query(ProjectSecurityGraphEdge.id)
        .filter_by(snapshot_id=snapshot_id, mapper_version=mapper_version)
        .count()
    )
    file_count = (
        db.session.query(ProjectSecurityGraphNode.file_path)
        .filter_by(snapshot_id=snapshot_id, mapper_version=mapper_version, node_type="file")
        .distinct()
        .count()
    )
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "file_count": file_count,
    }
