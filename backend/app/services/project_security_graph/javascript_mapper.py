"""JavaScript/TypeScript repository mapper: deterministic heuristic extraction.

Imports, function/class declarations and express/koa route registrations are
extracted with regex/text heuristics; every edge is marked ``heuristic`` and
never masquerades as an exact call graph.
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

EXTRACTOR = "js_heuristic"
LANGUAGE = "javascript"

_IMPORT_ES6_RE = re.compile(
    r"""^\s*import\s+(?:[^'"]*\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE
)
_IMPORT_REQUIRE_RE = re.compile(
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", re.MULTILINE
)
_FUNCTION_DECL_RE = re.compile(
    r"""\bfunction\s+([A-Za-z_$][\w$]*)""", re.MULTILINE
)
_CONST_FUNCTION_RE = re.compile(
    r"""\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>""",
    re.MULTILINE,
)
_CLASS_DECL_RE = re.compile(r"""\bclass\s+([A-Za-z_$][\w$]*)""", re.MULTILINE)
_ROUTE_CALL_RE = re.compile(
    r"""\b(?:app|router|route|server)\s*\.\s*(get|post|put|delete|patch|head|options|use|all)\s*\(\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_METHOD_RE = re.compile(r"""\b(?:exports\.|module\.exports\s*=\s*\{?\s*)([A-Za-z_$][\w$]*)""", re.MULTILINE)


def _line_of(match: re.Match) -> int:
    return len(match.string[: match.start()].splitlines())


def map_javascript_file(
    rel_path: str, source: str, budget: GraphBuildBudget
) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    lines = source.splitlines()
    if len(lines) > budget.max_lines:
        source = "\n".join(lines[: budget.max_lines])
    nodes: list[NodeDraft] = []
    edges: list[EdgeDraft] = []
    file_key = f"js:file:{rel_path}"
    nodes.append(
        NodeDraft(
            node_key=file_key,
            node_type=GraphNodeType.FILE,
            label=rel_path,
            file_path=rel_path,
            language=LANGUAGE,
            metadata={"imports": []},
        )
    )

    imports: list[dict] = nodes[0].metadata["imports"]
    for pattern in (_IMPORT_ES6_RE, _IMPORT_REQUIRE_RE):
        for match in pattern.finditer(source):
            imports.append(
                {"module": match.group(1), "names": [], "is_relative": match.group(1).startswith(("./", "../"))}
            )

    declared: dict[str, NodeDraft] = {}
    for pattern, kind in (
        (_FUNCTION_DECL_RE, "function"),
        (_CONST_FUNCTION_RE, "arrow"),
        (_CLASS_DECL_RE, "class"),
    ):
        for match in pattern.finditer(source):
            name = match.group(1)
            key = f"js:sym:{rel_path}:{name}"
            draft = NodeDraft(
                node_key=key,
                node_type=GraphNodeType.FUNCTION,
                label=name,
                file_path=rel_path,
                start_line=_line_of(match),
                language=LANGUAGE,
                metadata={"kind": kind},
            )
            nodes.append(draft)
            edges.append(
                EdgeDraft(
                    source_key=file_key,
                    target_key=key,
                    edge_type=GraphEdgeType.CONTAINS,
                    extractor=EXTRACTOR,
                    confidence=GraphConfidence.HEURISTIC,
                )
            )
            declared[name] = draft

    for match in _ROUTE_CALL_RE.finditer(source):
        method, rule = match.group(1).upper(), match.group(2)
        route_key = f"js:route:{rel_path}:{rule}:{method}"
        nodes.append(
            NodeDraft(
                node_key=route_key,
                node_type=GraphNodeType.ROUTE,
                label=f"{method} {rule}",
                file_path=rel_path,
                start_line=_line_of(match),
                language=LANGUAGE,
                metadata={"methods": [method], "rule": rule, "handler": None},
            )
        )

    return nodes, edges
