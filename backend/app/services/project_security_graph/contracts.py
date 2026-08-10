"""Shared contracts for the project security graph mappers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.project_security_graph import (
    GraphConfidence,
    GraphEdgeType,
    GraphNodeType,
)

DEFAULT_MAPPER_VERSION = "a4-v1"

# 建图预算默认值（防止超大仓库把内存/DB 打爆）
DEFAULT_MAX_NODES = 5000
DEFAULT_MAX_EDGES = 20000
DEFAULT_MAX_FILE_BYTES = 512 * 1024
DEFAULT_MAX_LINES = 4000
DEFAULT_MAX_NEIGHBOR_PAGE = 100

CODE_SLICE_MAX_LINES = 200
CODE_SLICE_MAX_REASON_CHARS = 200


@dataclass(frozen=True)
class GraphBuildBudget:
    max_nodes: int = DEFAULT_MAX_NODES
    max_edges: int = DEFAULT_MAX_EDGES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_lines: int = DEFAULT_MAX_LINES


@dataclass
class NodeDraft:
    node_key: str
    node_type: GraphNodeType | str
    label: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeDraft:
    source_key: str
    target_key: str
    edge_type: GraphEdgeType | str
    extractor: str
    confidence: GraphConfidence | str
    quality: int = 0


@dataclass
class GraphBuildResult:
    status: str  # cached | built | partial | cancelled | failed
    mapper_version: str
    node_count: int = 0
    edge_count: int = 0
    file_count: int = 0
    error_code: str | None = None
    message: str = ""


def _node_type_value(node_type: GraphNodeType | str) -> str:
    return node_type.value if isinstance(node_type, GraphNodeType) else node_type


def _edge_type_value(edge_type: GraphEdgeType | str) -> str:
    return edge_type.value if isinstance(edge_type, GraphEdgeType) else edge_type


def _confidence_value(confidence: GraphConfidence | str) -> str:
    return confidence.value if isinstance(confidence, GraphConfidence) else confidence


def module_to_path(module: str) -> list[str]:
    """Best-effort module name -> candidate file paths (relative, no extension resolution)."""
    normalized = module.strip().lstrip(".")
    if not normalized:
        return []
    dotted = normalized.replace(".", "/")
    return [f"{dotted}.py", f"{dotted}/__init__.py"]
