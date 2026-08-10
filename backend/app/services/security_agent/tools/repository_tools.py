"""map_repository tool: idempotently build the project security graph for a snapshot."""
from __future__ import annotations

from app.models.security import ProjectSnapshot
from app.services.project_security_graph.contracts import DEFAULT_MAPPER_VERSION
from app.services.project_security_graph.graph_builder import build_project_graph
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)


def build_map_repository_handler():
    def map_repository(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(
                status="failed", summary="任务已取消，未执行建图", error_code="AGENT_TOOL_FAILED"
            )
        snapshot = ProjectSnapshot.query.filter_by(id=ctx.snapshot_id).first()
        if snapshot is None:
            raise ToolExecutionError("快照不存在")

        def cancelled() -> bool:
            return ctx.cancelled()

        result = build_project_graph(
            snapshot,
            mapper_version=DEFAULT_MAPPER_VERSION,
            is_cancelled=cancelled,
        )
        if result.status == "failed":
            raise ToolExecutionError(result.message, warning_code=result.error_code or "AGENT_TOOL_FAILED")
        return ToolResult(
            status="succeeded" if result.status in {"built", "cached"} else "partial",
            summary=(
                f"建图{'完成（命中缓存）' if result.status == 'cached' else '完成'}"
                f"：{result.node_count} 节点 / {result.edge_count} 边 / {result.file_count} 文件"
                + (f"（{result.message}）" if result.message else "")
            ),
            artifact_refs=[
                {
                    "artifact_type": "security_graph",
                    "summary": f"{result.node_count} nodes, {result.edge_count} edges",
                    "mapper_version": result.mapper_version,
                }
            ],
            warning_codes=([result.error_code] if result.error_code else []),
            metrics={
                "status": result.status,
                "node_count": result.node_count,
                "edge_count": result.edge_count,
                "file_count": result.file_count,
                "mapper_version": result.mapper_version,
            },
        )

    return map_repository
