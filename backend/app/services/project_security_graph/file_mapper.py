"""File-level dispatch: route a source file to the right language mapper."""
from __future__ import annotations

from app.services.project_security_graph.contracts import EdgeDraft, GraphBuildBudget, NodeDraft
from app.services.project_security_graph.java_go_mapper import map_go_file, map_java_file
from app.services.project_security_graph.javascript_mapper import map_javascript_file
from app.services.project_security_graph.python_mapper import map_python_file

_PYTHON_EXTENSIONS = frozenset({".py", ".pyi"})
_JAVASCRIPT_EXTENSIONS = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
_JAVA_EXTENSIONS = frozenset({".java"})
_GO_EXTENSIONS = frozenset({".go"})

# 不建图的扩展名（二进制/产物/依赖目录），避免把 vendor 内容塞进图
_SKIP_DIRECTORY_SEGMENTS = frozenset(
    {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build", "target", "vendor"}
)


def is_skipped_path(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    return any(segment in _SKIP_DIRECTORY_SEGMENTS for segment in parts)


def map_file(
    rel_path: str,
    extension: str | None,
    source: str,
    budget: GraphBuildBudget,
) -> tuple[list[NodeDraft], list[EdgeDraft]] | None:
    """Return (nodes, edges) for one text file, or None when the language is unsupported."""
    if is_skipped_path(rel_path):
        return None
    ext = (extension or "").lower()
    if ext in _PYTHON_EXTENSIONS:
        return map_python_file(rel_path, source, budget)
    if ext in _JAVASCRIPT_EXTENSIONS:
        return map_javascript_file(rel_path, source, budget)
    if ext in _JAVA_EXTENSIONS:
        return map_java_file(rel_path, source, budget)
    if ext in _GO_EXTENSIONS:
        return map_go_file(rel_path, source, budget)
    return None
