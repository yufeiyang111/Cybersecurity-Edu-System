"""finalize_agent_report: deterministic internal step that materializes the run summary."""
from __future__ import annotations

from app.models.agent_runtime import AgentRun
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)


def build_report_handler():
    def finalize_agent_report(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消，未生成报告", error_code="AGENT_TOOL_FAILED")

        run = AgentRun.query.filter_by(id=ctx.run.id).first()
        if run is None:
            raise ToolExecutionError("运行记录不存在，无法生成报告")

        payload = {
            "run_id": run.id,
            "mode": run.mode.value if hasattr(run.mode, "value") else run.mode,
            "goal": run.goal_text[:200],
            "tool_call_count": run.tool_call_count,
            "completed_at": run.finished_at.isoformat() if run.finished_at else None,
        }
        return ToolResult(
            status="succeeded",
            summary="运行摘要已生成",
            artifact_refs=[
                {
                    "artifact_type": "agent_report",
                    "summary": f"run #{run.id} 运行摘要",
                }
            ],
            metrics=payload,
        )

    return finalize_agent_report
