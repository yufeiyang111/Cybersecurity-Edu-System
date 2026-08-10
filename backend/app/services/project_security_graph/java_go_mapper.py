"""Java / Go repository mappers: first-pass partial extraction.

Only file nodes plus import/class declarations are extracted; every result is
marked ``partial``. Full symbol/call resolution is deferred to a later batch.
"""
from __future__ import annotations

import re

from app.services.project_security_graph.contracts import (
    EdgeDraft,
    GraphBuildBudget,
    GraphConfidence,
    GraphEdgeType,
    GraphNodeType,
    NodeDraft,
)

JAVA_EXTRACTOR = "java_partial"
JAVA_LANGUAGE = "java"
_GO_EXTRACTOR = "go_partial"
_GO_LANGUAGE = "go"

_JAVA_CLASS_RE = re.compile(r"""\b(class|interface|enum)\s+([A-Za-z_$][\w$]*)""", re.MULTILINE)
_GO_FUNC_RE = re.compile(
    r"""^func\s+(?:\([^)]*\)\s*)?([A-Za-z_$][\w$]*)""", re.MULTILINE
)
_GO_TYPE_RE = re.compile(r"""^type\s+([A-Za-z_$][\w$]*)""", re.MULTILINE)


def _line_of(match: re.Match, source: str) -> int:
    return len(source[: match.start()].splitlines())


def map_java_file(
    rel_path: str, source: str, budget: GraphBuildBudget
) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    lines = source.splitlines()
    if len(lines) > budget.max_lines:
        source = "\n".join(lines[: budget.max_lines])
    nodes: list[NodeDraft] = []
    file_key = f"java:file:{rel_path}"
    nodes.append(
        NodeDraft(
            node_key=file_key,
            node_type=GraphNodeType.FILE,
            label=rel_path,
            file_path=rel_path,
            language=JAVA_LANGUAGE,
            metadata={"imports": []},
        )
    )
    for match in _JAVA_CLASS_RE.finditer(source):
        kind, name = match.group(1), match.group(2)
        nodes.append(
            NodeDraft(
                node_key=f"java:class:{rel_path}:{name}",
                node_type=GraphNodeType.FUNCTION,
                label=name,
                file_path=rel_path,
                start_line=_line_of(match, source),
                language=JAVA_LANGUAGE,
                metadata={"kind": f"java_{kind}", "partial": True},
            )
        )
    return nodes, []


def map_go_file(
    rel_path: str, source: str, budget: GraphBuildBudget
) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    lines = source.splitlines()
    if len(lines) > budget.max_lines:
        source = "\n".join(lines[: budget.max_lines])
    nodes: list[NodeDraft] = []
    file_key = f"go:file:{rel_path}"
    nodes.append(
        NodeDraft(
            node_key=file_key,
            node_type=GraphNodeType.FILE,
            label=rel_path,
            file_path=rel_path,
            language=_GO_LANGUAGE,
            metadata={"imports": []},
        )
    )
    for pattern in (_GO_FUNC_RE, _GO_TYPE_RE):
        for match in pattern.finditer(source):
            name = match.group(1)
            nodes.append(
                NodeDraft(
                    node_key=f"go:sym:{rel_path}:{name}",
                    node_type=GraphNodeType.FUNCTION,
                    label=name,
                    file_path=rel_path,
                    start_line=_line_of(match, source),
                    language=_GO_LANGUAGE,
                    metadata={"partial": True},
                )
            )
    return nodes, []
