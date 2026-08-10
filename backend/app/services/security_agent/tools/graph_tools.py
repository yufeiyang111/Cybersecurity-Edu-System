"""Graph browsing tools: paged route/symbol/relation queries for the agent."""
from __future__ import annotations

import sqlalchemy as sa

from app import db
from app.models.project_security_graph import ProjectSecurityGraphNode
from app.services.project_security_graph import graph_queries
from app.services.project_security_graph.contracts import (
    DEFAULT_MAPPER_VERSION,
    DEFAULT_MAX_NEIGHBOR_PAGE,
)
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)

_MAX_TOOL_PAGE = DEFAULT_MAX_NEIGHBOR_PAGE
_MAX_DEPTH = 8
_UPSTREAM_EDGE_TYPES = ["calls", "calls_into", "imports"]


def _page_params(input: dict) -> tuple[int, int]:
    limit = int(input.get("limit") or 20)
    offset = int(input.get("offset") or 0)
    if not 1 <= limit <= _MAX_TOOL_PAGE or offset < 0:
        raise ToolExecutionError("limit 必须在 1 至 100 之间，offset 不能小于 0")
    return limit, offset


def _require_graph(snapshot_id: int, mapper_version: str) -> None:
    if graph_queries.graph_summary(snapshot_id, mapper_version) is None:
        raise ToolExecutionError(
            "该快照尚未建图，请先执行 map_repository",
            warning_code="AGENT_GRAPH_NOT_BUILT",
        )


def build_get_route_map_handler():
    def get_route_map(ctx: ToolExecutionContext) -> ToolResult:
        _require_graph(ctx.snapshot_id, DEFAULT_MAPPER_VERSION)
        limit, offset = _page_params(ctx.input)
        nodes, total = graph_queries.entry_nodes(
            ctx.snapshot_id, DEFAULT_MAPPER_VERSION, limit, offset
        )
        return ToolResult(
            status="succeeded",
            summary=f"路由/文件入口节点 {total} 个",
            metrics={
                "pagination": {"total": total, "limit": limit, "offset": offset},
                "nodes": [node.to_dict() for node in nodes],
            },
        )

    return get_route_map


def build_get_authentication_map_handler():
    def get_authentication_map(ctx: ToolExecutionContext) -> ToolResult:
        _require_graph(ctx.snapshot_id, DEFAULT_MAPPER_VERSION)
        limit, offset = _page_params(ctx.input)
        nodes, total = graph_queries.entry_nodes(
            ctx.snapshot_id, DEFAULT_MAPPER_VERSION, limit, offset
        )
        auth_nodes = [
            node.to_dict()
            for node in nodes
            if node.node_type in {"route", "middleware"}
            or "auth" in (node.label or "").lower()
            or "login" in (node.label or "").lower()
        ]
        return ToolResult(
            status="succeeded",
            summary=f"鉴权相关节点 {len(auth_nodes)} 个（启发式过滤）",
            metrics={
                "nodes": auth_nodes,
                "pagination": {"total": len(auth_nodes), "limit": limit, "offset": offset},
            },
        )

    return get_authentication_map


def build_find_symbol_references_handler():
    def find_symbol_references(ctx: ToolExecutionContext) -> ToolResult:
        symbol = (ctx.input.get("symbol") or "").strip()
        if not symbol or len(symbol) > 512:
            raise ToolExecutionError("symbol 必填且不能超过 512 字符")
        limit, offset = _page_params(ctx.input)
        edges, total = graph_queries.incoming_edges_for_label(
            ctx.snapshot_id, DEFAULT_MAPPER_VERSION, symbol, limit, offset
        )
        return ToolResult(
            status="succeeded",
            summary=f"符号 {symbol} 的引用 {total} 条",
            metrics={
                "symbol": symbol,
                "pagination": {"total": total, "limit": limit, "offset": offset},
                "references": [edge.to_dict() for edge in edges],
            },
        )

    return find_symbol_references


def build_get_related_files_handler():
    def get_related_files(ctx: ToolExecutionContext) -> ToolResult:
        file_path = (ctx.input.get("file_path") or "").strip()
        if not file_path or len(file_path) > 512:
            raise ToolExecutionError("file_path 必填且不能超过 512 字符")
        nodes = graph_queries.nodes_for_file(
            ctx.snapshot_id, DEFAULT_MAPPER_VERSION, file_path
        )
        return ToolResult(
            status="succeeded",
            summary=f"文件 {file_path} 关联节点 {len(nodes)} 个",
            metrics={"file_path": file_path, "nodes": [node.to_dict() for node in nodes]},
        )

    return get_related_files


def build_call_chain_handler():
    def call_chain(ctx: ToolExecutionContext) -> ToolResult:
        label = (ctx.input.get("symbol") or "").strip()
        if not label or len(label) > 512:
            raise ToolExecutionError("symbol 必填且不能超过 512 字符")
        depth = int(ctx.input.get("depth") or 3)
        if not 1 <= depth <= _MAX_DEPTH:
            raise ToolExecutionError(f"depth 必须在 1 至 {_MAX_DEPTH} 之间")
        edges, _ = graph_queries.incoming_edges_for_label(
            ctx.snapshot_id, DEFAULT_MAPPER_VERSION, label, _MAX_TOOL_PAGE, 0
        )
        chain: list[dict] = []
        visited: set[int] = set()
        frontier: list[int] = [edge.source_node_id for edge in edges]
        for _ in range(depth):
            next_frontier: list[int] = []
            for node_id in frontier:
                if node_id in visited:
                    continue
                visited.add(node_id)
                node = graph_queries.node_or_none(
                    node_id, ctx.snapshot_id, DEFAULT_MAPPER_VERSION
                )
                if node is None:
                    continue
                chain.append(node.to_dict())
                upstream, _ = graph_queries.node_neighbors(
                    node, _MAX_TOOL_PAGE, 0, _UPSTREAM_EDGE_TYPES
                )
                next_frontier.extend(edge.source_node_id for edge in upstream)
            frontier = next_frontier
        return ToolResult(
            status="succeeded",
            summary=f"调用链分析：{label} 上游 {len(chain)} 个节点（深度 {depth}）",
            metrics={"symbol": label, "chain": chain},
        )

    return call_chain


def build_search_code_handler():
    def search_code(ctx: ToolExecutionContext) -> ToolResult:
        query = (ctx.input.get("query") or "").strip()
        if not query or len(query) > 128:
            raise ToolExecutionError("query 必填且不能超过 128 字符")
        limit, offset = _page_params(ctx.input)
        conditions = sa.or_(
            ProjectSecurityGraphNode.label.ilike(f"%{query}%"),
            ProjectSecurityGraphNode.file_path.ilike(f"%{query}%"),
        )
        total = (
            db.session.query(ProjectSecurityGraphNode.id)
            .filter(
                ProjectSecurityGraphNode.snapshot_id == ctx.snapshot_id,
                ProjectSecurityGraphNode.mapper_version == DEFAULT_MAPPER_VERSION,
                conditions,
            )
            .count()
        )
        nodes = (
            ProjectSecurityGraphNode.query.filter(
                ProjectSecurityGraphNode.snapshot_id == ctx.snapshot_id,
                ProjectSecurityGraphNode.mapper_version == DEFAULT_MAPPER_VERSION,
                conditions,
            )
            .order_by(ProjectSecurityGraphNode.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ToolResult(
            status="succeeded",
            summary=f"搜索 {query}：命中 {total} 个节点",
            metrics={
                "query": query,
                "pagination": {"total": total, "limit": limit, "offset": offset},
                "nodes": [node.to_dict() for node in nodes],
            },
        )

    return search_code
