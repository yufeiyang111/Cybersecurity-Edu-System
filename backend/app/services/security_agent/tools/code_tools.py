"""read_code_slice tool: restricted source evidence via the shared code-slice gate."""
from __future__ import annotations

from app.models.security import ProjectSnapshot
from app.services.project_security_graph.code_slice import (
    CodeSliceError,
    CodeSliceForbidden,
    read_code_slice,
)
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)


def build_read_code_slice_handler():
    def read_code_slice_tool(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(
                status="failed", summary="任务已取消，未读取代码", error_code="AGENT_TOOL_FAILED"
            )
        file_path = (ctx.input.get("file_path") or "").strip()
        start_line = ctx.input.get("start_line")
        end_line = ctx.input.get("end_line")
        reason = (ctx.input.get("reason") or "").strip()
        if not file_path or len(file_path) > 512:
            raise ToolExecutionError("file_path 必填且不能超过 512 字符")
        try:
            start_line = int(start_line)
            end_line = int(end_line)
        except (TypeError, ValueError):
            raise ToolExecutionError("start_line/end_line 必须是整数")
        snapshot = ProjectSnapshot.query.filter_by(id=ctx.snapshot_id).first()
        if snapshot is None:
            raise ToolExecutionError("快照不存在")
        try:
            payload = read_code_slice(snapshot, file_path, start_line, end_line, reason)
        except CodeSliceForbidden as exc:
            raise ToolExecutionError(str(exc), warning_code="AGENT_CODE_SLICE_FORBIDDEN") from exc
        except CodeSliceError as exc:
            raise ToolExecutionError(str(exc), warning_code="AGENT_CODE_SLICE_INVALID") from exc
        line_count = len(payload["lines"])
        return ToolResult(
            status="succeeded",
            summary=f"读取 {file_path} 第 {start_line}-{end_line} 行（{line_count} 行）",
            metrics={
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "reason": reason,
                "line_count": line_count,
                "lines": payload["lines"],
            },
        )

    return read_code_slice_tool
