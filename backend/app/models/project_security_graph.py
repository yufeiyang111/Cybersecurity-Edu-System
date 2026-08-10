"""Persistence models for the project security graph (A4)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class GraphNodeType(str, Enum):
    ROUTE = "route"
    MIDDLEWARE = "middleware"
    SERVICE = "service"
    REPOSITORY = "repository"
    MODEL = "model"
    FUNCTION = "function"
    DEPENDENCY = "dependency"
    EXTERNAL_CALL = "external_call"
    FILE = "file"


class GraphEdgeType(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    DECORATED_BY = "decorated_by"
    ROUTE_HANDLES = "route_handles"
    CONTAINS = "contains"
    HAS_DEPENDENCY = "has_dependency"
    CALLS_INTO = "calls_into"


class GraphConfidence(str, Enum):
    EXACT = "exact"
    HEURISTIC = "heuristic"
    PARTIAL = "partial"


_BIGINT = db.BigInteger().with_variant(db.Integer, "sqlite")


class ProjectSecurityGraphNode(db.Model):
    """One symbol / file / route / dependency node in a snapshot graph."""

    __tablename__ = "project_security_graph_nodes"
    __table_args__ = (
        db.UniqueConstraint(
            "snapshot_id", "mapper_version", "node_key", name="uq_graph_nodes_scope"
        ),
        db.Index("ix_graph_nodes_snapshot_type", "snapshot_id", "mapper_version", "node_type"),
        db.Index("ix_graph_nodes_snapshot_file", "snapshot_id", "file_path"),
    )

    id = db.Column(_BIGINT, primary_key=True)
    snapshot_id = db.Column(
        db.Integer, db.ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    mapper_version = db.Column(db.String(64), nullable=False)
    node_key = db.Column(db.String(512), nullable=False)
    node_type = db.Column(
        db.Enum(GraphNodeType, name="graph_node_type", values_callable=_enum_values),
        nullable=False,
    )
    label = db.Column(db.String(512), nullable=False)
    file_path = db.Column(db.String(512))
    start_line = db.Column(db.Integer)
    end_line = db.Column(db.Integer)
    language = db.Column(db.String(32))
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    snapshot = db.relationship("ProjectSnapshot")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "snapshot_id": self.snapshot_id,
            "mapper_version": self.mapper_version,
            "node_key": self.node_key,
            "node_type": self.node_type.value if isinstance(self.node_type, Enum) else self.node_type,
            "label": self.label,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "metadata": self.metadata_json or {},
        }


class ProjectSecurityGraphEdge(db.Model):
    """One directed relation between two graph nodes."""

    __tablename__ = "project_security_graph_edges"
    __table_args__ = (
        db.Index("ix_graph_edges_snapshot_source", "snapshot_id", "source_node_id"),
        db.Index("ix_graph_edges_snapshot_target", "snapshot_id", "target_node_id"),
    )

    id = db.Column(_BIGINT, primary_key=True)
    snapshot_id = db.Column(
        db.Integer, db.ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    mapper_version = db.Column(db.String(64), nullable=False)
    source_node_id = db.Column(
        _BIGINT, db.ForeignKey("project_security_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id = db.Column(
        _BIGINT, db.ForeignKey("project_security_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type = db.Column(
        db.Enum(GraphEdgeType, name="graph_edge_type", values_callable=_enum_values),
        nullable=False,
    )
    extractor = db.Column(db.String(64), nullable=False)
    confidence = db.Column(
        db.Enum(GraphConfidence, name="graph_confidence", values_callable=_enum_values),
        nullable=False,
    )
    quality = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    snapshot = db.relationship("ProjectSnapshot")
    source_node = db.relationship(
        "ProjectSecurityGraphNode", foreign_keys=[source_node_id], lazy="joined"
    )
    target_node = db.relationship(
        "ProjectSecurityGraphNode", foreign_keys=[target_node_id], lazy="joined"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "snapshot_id": self.snapshot_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_type": self.edge_type.value if isinstance(self.edge_type, Enum) else self.edge_type,
            "extractor": self.extractor,
            "confidence": self.confidence.value
            if isinstance(self.confidence, Enum)
            else self.confidence,
            "quality": self.quality,
            "source_label": self.source_node.label if self.source_node else None,
            "target_label": self.target_node.label if self.target_node else None,
        }
