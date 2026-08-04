"""Risk tools: rank persisted findings with the shared explainable risk scorer."""
from __future__ import annotations

from app import db
from app.models.security import ScanTask, SecurityFinding
from app.services.risk_scoring import score_finding
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)


def _latest_task(ctx: ToolExecutionContext) -> ScanTask:
    task = (
        ScanTask.query.filter_by(snapshot_id=ctx.snapshot_id)
        .order_by(ScanTask.id.desc())
        .first()
    )
    if task is None:
        raise ToolExecutionError("该快照还没有扫描任务，无法排序风险")
    return task


def _scored(findings: list[SecurityFinding]) -> list[dict]:
    scored = []
    for finding in findings:
        risk = score_finding(finding)
        scored.append(
            {
                "id": finding.id,
                "rule_id": finding.rule_id,
                "severity": finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
                "category": finding.category.value if hasattr(finding.category, "value") else str(finding.category),
                "file_path": finding.file_path,
                "start_line": finding.start_line,
                "message": finding.message[:120],
                "risk_score": risk.score if hasattr(risk, "score") else None,
                "priority": risk.priority if hasattr(risk, "priority") else None,
            }
        )
    return sorted(
        scored,
        key=lambda item: (item.get("risk_score") is None, -(item.get("risk_score") or 0)),
    )


def build_rank_findings_handler():
    def rank_findings(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消", error_code="AGENT_TOOL_FAILED")
        task = _latest_task(ctx)
        findings = SecurityFinding.query.filter_by(task_id=task.id).order_by(SecurityFinding.id.asc()).all()
        ranked = _scored(findings)
        critical = sum(1 for item in ranked if (item.get("risk_score") or 0) >= 80)
        high = sum(1 for item in ranked if 60 <= (item.get("risk_score") or 0) < 80)
        return ToolResult(
            status="succeeded",
            summary=f"风险排序完成：{len(ranked)} 个发现，严重 {critical}，高危 {high}",
            artifact_refs=[
                {
                    "artifact_type": "risk_ranking",
                    "summary": f"{len(ranked)} findings ranked",
                }
            ],
            metrics={
                "task_id": task.id,
                "ranked_count": len(ranked),
                "critical": critical,
                "high": high,
                "top_ranked": ranked[:10],
            },
        )

    return rank_findings


def build_findings_handler():
    def get_findings(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消", error_code="AGENT_TOOL_FAILED")
        task = _latest_task(ctx)
        findings = SecurityFinding.query.filter_by(task_id=task.id).order_by(SecurityFinding.id.asc()).all()
        counts: dict[str, int] = {}
        for finding in findings:
            severity = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
            counts[severity] = counts.get(severity, 0) + 1
        return ToolResult(
            status="succeeded",
            summary=f"查询到 {len(findings)} 个发现：{counts}",
            metrics={
                "task_id": task.id,
                "findings_count": len(findings),
                "severity_counts": counts,
            },
        )

    return get_findings
