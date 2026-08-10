"""Python repository mapper: stdlib ``ast`` based symbol, route and call graph extraction.

Never executes code. Emits NodeDraft/EdgeDraft with exact confidence only when the
AST is unambiguous; anything uncertain is either skipped or marked heuristic.
"""
from __future__ import annotations

import ast
from typing import Any

from app.services.project_security_graph.contracts import (
    EdgeDraft,
    GraphBuildBudget,
    GraphConfidence,
    GraphEdgeType,
    GraphNodeType,
    NodeDraft,
    _confidence_value,
    _edge_type_value,
    _node_type_value,
)

EXTRACTOR = "python_ast"
LANGUAGE = "python"

ROUTE_DECORATOR_NAMES = frozenset(
    {"route", "get", "post", "put", "delete", "patch", "head", "options"}
)
MODEL_BASE_HINTS = frozenset({"db.Model", "Model", "DeclarativeBase", "SQLAlchemy"})
MODEL_NAME_HINTS = frozenset({"model", "models"})
SERVICE_NAME_HINTS = frozenset({"service", "services"})
REPOSITORY_NAME_HINTS = frozenset({"repository", "repositories", "repo"})
MIDDLEWARE_NAME_HINTS = frozenset({"middleware"})


def _infer_class_type(class_name: str, bases: list[str], module_imports: list[str]) -> str:
    lowered = class_name.lower()
    if "middleware" in lowered or any("middleware" in base.lower() for base in bases):
        return _node_type_value(GraphNodeType.MIDDLEWARE)
    if "repository" in lowered:
        return _node_type_value(GraphNodeType.REPOSITORY)
    if "service" in lowered:
        return _node_type_value(GraphNodeType.SERVICE)
    for base in bases:
        base_tail = base.split(".")[-1]
        if base in MODEL_BASE_HINTS or base_tail in {"Model", "Base"}:
            return _node_type_value(GraphNodeType.MODEL)
    if any(hint in lowered for hint in MODEL_NAME_HINTS):
        return _node_type_value(GraphNodeType.MODEL)
    return _node_type_value(GraphNodeType.FUNCTION)


def _route_methods(dec: ast.Call) -> str | None:
    """Extract HTTP methods from a route decorator call; None when it is not a route decorator."""
    func = dec.func
    if not isinstance(func, ast.Attribute):
        return None
    attr = func.attr
    if attr not in ROUTE_DECORATOR_NAMES:
        return None
    if attr == "route":
        methods = []
        for keyword in dec.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                for item in keyword.value.elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        methods.append(item.value.upper())
        return ",".join(sorted(methods)) if methods else "ANY"
    return attr.upper()


def _first_string_arg(dec: ast.Call) -> str | None:
    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
        return dec.args[0].value
    return None


def _collect_imports(tree: ast.Module) -> list[dict[str, Any]]:
    """Collect imports as: {module, names, aliases(module-level), is_relative}."""
    imports: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "module": alias.name,
                        "names": [alias.asname or alias.name],
                        "aliases": {alias.asname or alias.name: alias.name},
                        "is_relative": False,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            imports.append(
                {
                    "module": node.module,
                    "names": [alias.asname or alias.name for alias in node.names],
                    "aliases": {
                        (alias.asname or alias.name): alias.name for alias in node.names
                    },
                    "is_relative": bool(node.level),
                }
            )
    return imports


class _FileGraphBuilder:
    """Collects nodes/edges for one Python file; cross-file edges resolve later."""

    def __init__(self, rel_path: str, source: str, budget: GraphBuildBudget) -> None:
        self.rel_path = rel_path
        self.source = source
        self.budget = budget
        self.nodes: list[NodeDraft] = []
        self.edges: list[EdgeDraft] = []
        self.symbols: dict[str, NodeDraft] = {}  # top-level function/class name -> node
        self.file_key = f"py:file:{rel_path}"

    def build(self) -> None:
        lines = self.source.splitlines()
        if len(lines) > self.budget.max_lines:
            lines = lines[: self.budget.max_lines]
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            return

        imports = _collect_imports(tree)
        self.nodes.append(
            NodeDraft(
                node_key=self.file_key,
                node_type=GraphNodeType.FILE,
                label=self.rel_path,
                file_path=self.rel_path,
                language=LANGUAGE,
                metadata={"imports": imports},
            )
        )

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_top_level_function(node)
            elif isinstance(node, ast.ClassDef):
                self._add_class(node)

        self._resolve_same_file_edges()
        self._resolve_route_edges()

    def _add_top_level_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        key = f"py:func:{self.rel_path}:{node.name}"
        draft = NodeDraft(
            node_key=key,
            node_type=GraphNodeType.FUNCTION,
            label=node.name,
            file_path=self.rel_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            language=LANGUAGE,
            metadata={"kind": "function", "calls": self._collect_calls(node)},
        )
        self.nodes.append(draft)
        self.symbols[node.name] = draft
        self.edges.append(
            EdgeDraft(
                source_key=self.file_key,
                target_key=key,
                edge_type=GraphEdgeType.CONTAINS,
                extractor=EXTRACTOR,
                confidence=GraphConfidence.EXACT,
            )
        )

    def _add_class(self, node: ast.ClassDef) -> None:
        bases = [self._base_name(base) for base in node.bases]
        inferred = _infer_class_type(node.name, bases, [])
        key = f"py:class:{self.rel_path}:{node.name}"
        draft = NodeDraft(
            node_key=key,
            node_type=inferred,
            label=node.name,
            file_path=self.rel_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            language=LANGUAGE,
            metadata={"kind": "class", "bases": bases},
        )
        self.nodes.append(draft)
        self.symbols[node.name] = draft
        self.edges.append(
            EdgeDraft(
                source_key=self.file_key,
                target_key=key,
                edge_type=GraphEdgeType.CONTAINS,
                extractor=EXTRACTOR,
                confidence=GraphConfidence.EXACT,
            )
        )
        for base in bases:
            base_tail = base.split(".")[-1]
            if base_tail in self.symbols:
                self.edges.append(
                    EdgeDraft(
                        source_key=key,
                        target_key=self.symbols[base_tail].node_key,
                        edge_type=GraphEdgeType.INHERITS,
                        extractor=EXTRACTOR,
                        confidence=GraphConfidence.EXACT,
                    )
                )

        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_key = f"py:func:{self.rel_path}:{node.name}.{member.name}"
                method = NodeDraft(
                    node_key=method_key,
                    node_type=GraphNodeType.FUNCTION,
                    label=f"{node.name}.{member.name}",
                    file_path=self.rel_path,
                    start_line=member.lineno,
                    end_line=member.end_lineno,
                    language=LANGUAGE,
                    metadata={
                        "kind": "method",
                        "class_of": node.name,
                        "calls": self._collect_calls(member, class_name=node.name),
                    },
                )
                self.nodes.append(method)
                self.symbols[f"{node.name}.{member.name}"] = method
                self.edges.append(
                    EdgeDraft(
                        source_key=key,
                        target_key=method_key,
                        edge_type=GraphEdgeType.CONTAINS,
                        extractor=EXTRACTOR,
                        confidence=GraphConfidence.EXACT,
                    )
                )

    def _resolve_same_file_edges(self) -> None:
        """Function/method -> function/method calls within the same file.

        ``ClassName.method`` candidates match exactly; bare method tails only
        match when the tail is unique in the file. Ambiguous names are skipped
        so the graph never fabricates edges.
        """
        exact: dict[str, str] = {
            key: symbol.node_key
            for key, symbol in self.symbols.items()
            if "." in key
        }
        tails: dict[str, list[str]] = {}
        for key, symbol in self.symbols.items():
            if "." in key:
                tails.setdefault(key.split(".")[-1], []).append(symbol.node_key)

        for symbol_key, symbol in list(self.symbols.items()):
            metadata = symbol.metadata or {}
            for call_name in metadata.get("calls", []):
                target_key = self._match_call_target(
                    call_name, exact, tails
                )
                if target_key is not None and target_key != symbol.node_key:
                    self.edges.append(
                        EdgeDraft(
                            source_key=symbol.node_key,
                            target_key=target_key,
                            edge_type=GraphEdgeType.CALLS,
                            extractor=EXTRACTOR,
                            confidence=GraphConfidence.EXACT,
                        )
                    )

    @staticmethod
    def _match_call_target(
        call_name: str,
        exact: dict[str, str],
        tails: dict[str, list[str]],
    ) -> str | None:
        if "." in call_name:
            matched = exact.get(call_name)
            if matched is not None:
                return matched
        matches = tails.get(call_name, [])
        if len(matches) == 1:
            return matches[0]
        return None

    def _resolve_route_edges(self) -> None:
        """Route decorator detection: build route nodes and connect to handlers."""
        try:
            tree = ast.parse("\n".join(self.source.splitlines()[: self.budget.max_lines]))
        except SyntaxError:
            return
        routes: list[tuple[NodeDraft, str]] = []  # (route node, handler name)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    methods = _route_methods(decorator)
                    if methods is None:
                        continue
                    rule = _first_string_arg(decorator)
                    if rule is None:
                        continue
                    route_key = (
                        f"py:route:{self.rel_path}:{rule}:{methods}"
                    )
                    route = NodeDraft(
                        node_key=route_key,
                        node_type=GraphNodeType.ROUTE,
                        label=f"{methods} {rule}",
                        file_path=self.rel_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno,
                        language=LANGUAGE,
                        metadata={
                            "methods": methods.split(",") if methods != "ANY" else ["ANY"],
                            "rule": rule,
                            "handler": node.name,
                        },
                    )
                    self.nodes.append(route)
                    routes.append((route, node.name))

        for route, handler in routes:
            handler_key = f"py:func:{self.rel_path}:{handler}"
            if handler_key in {n.node_key for n in self.nodes}:
                self.edges.append(
                    EdgeDraft(
                        source_key=route.node_key,
                        target_key=handler_key,
                        edge_type=GraphEdgeType.ROUTE_HANDLES,
                        extractor=EXTRACTOR,
                        confidence=GraphConfidence.EXACT,
                    )
                )

    def _collect_calls(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str | None = None
    ) -> list[str]:
        """Candidate callee names inside the function body.

        ``self.x`` chains resolve to ``ClassName.x`` when a class context is
        known; other attribute chains contribute their tail name only when it
        is unambiguous at resolve time.
        """
        calls: list[str] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                candidate = self._attribute_call_name(child.func, class_name)
                calls.append(candidate)
                if "." in candidate and candidate.startswith(f"{class_name}."):
                    calls.append(candidate.rsplit(".", 1)[-1])
        return calls

    @staticmethod
    def _attribute_call_name(func: ast.Attribute, class_name: str | None) -> str:
        parts: list[str] = []
        current: ast.expr = func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            if current.id == "self" and class_name:
                tail = ".".join(reversed(parts))
                return f"{class_name}.{tail}"
            parts.append(current.id)
        return ".".join(reversed(parts))

    @staticmethod
    def _base_name(base: ast.expr) -> str:
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            parts = [base.attr]
            current = base.value
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return "<expr>"


def map_python_file(
    rel_path: str, source: str, budget: GraphBuildBudget
) -> tuple[list[NodeDraft], list[EdgeDraft]]:
    builder = _FileGraphBuilder(rel_path, source, budget)
    builder.build()
    return builder.nodes, builder.edges
