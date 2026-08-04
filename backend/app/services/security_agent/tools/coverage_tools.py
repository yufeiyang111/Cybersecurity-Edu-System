"""Coverage tools: report what was actually scanned, not only files with findings."""
from __future__ import annotations

from app import db
from app.models.security import ScanTask
from app.services.scan_coverage.summary import coverage_summary, list_coverage_files
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)


def _resolve_task(ctx: ToolExecutionContext, task_id: int | None) -> ScanTask:
    candidate_id = task_id or ctx.input.get("task_id")
    if candidate_id:
        task = db.session.get(ScanTask, int(candidate_id))
        if task is not None and task.snapshot_id == ctx.snapshot_id:
            return task
    latest = (
        ScanTask.query.filter_by(snapshot_id=ctx.snapshot_id)
        .order_by(ScanTask.id.desc())
        .first()
    )
    if latest is None:
        raise ToolExecutionError("该快照还没有扫描任务，无法生成覆盖报告")
    return latest


def build_coverage_handler():
    def get_scan_coverage(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消", error_code="AGENT_TOOL_FAILED")
        task = _resolve_task(ctx, None)
        summary = coverage_summary(task)
        kinds = ["baseline_scanned", "specialized_sast", "generic_only", "scanned_no_finding", "scanned_with_findings", "excluded"]
        summary_text = "覆盖报告："
        summary_text += "、".join(
            f"{summary.get(kind, 0)} 个{_kind_label(kind)}" for kind in kinds if summary.get(kind, 0)
        ) or "暂无收据"
        return ToolResult(
            status="succeeded",
            summary=summary_text,
            artifact_refs=[
                {
                    "artifact_type": "coverage_report",
                    "summary": f"task #{task.id}: {summary['total_files']} files",
                }
            ],
            metrics=summary,
        )

    return get_scan_coverage


def _kind_label(kind: str) -> str:
    labels = {
        "baseline_scanned": "基线覆盖",
        "specialized_sast": "专用 SAST",
        "generic_only": "通用扫描",
        "scanned_no_finding": "无发现文件",
        "scanned_with_findings": "有发现文件",
        "excluded": "排除",
        "skipped": "跳过",
        "failed": "失败",
    }
    return labels.get(kind, kind)
