"""Deterministic scan tools: real scanners driven through the existing pipeline."""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.security import ScanTask, ScanTaskStatus, SnapshotDependency
from app.services.scan_coverage.catalog import catalog_snapshot_files
from app.services.scan_coverage.receipts import write_coverage_receipts_for_task
from app.services.scan_execution import execute_scan_stages
from app.services.scan_orchestrator import run_scan_task
from app.services.scan_exclusion import GitignoreMatcher
from app.services.scanners import get_scanners
from app.services.scanners.registry import descriptor_for
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

UNIVERSAL_SECRET_SCANNER_NAME = "universal_secret"


def _task_exclusion_matcher(ctx: ToolExecutionContext) -> GitignoreMatcher | None:
    from app.models.security import SecurityProject

    project = SecurityProject.query.filter_by(id=ctx.project_id).first()
    if project is None:
        return None
    patterns = [rule.pattern for rule in project.exclusion_rules]
    if not patterns:
        return None
    return GitignoreMatcher.from_patterns(patterns)


def build_baseline_scan_handler():
    def run_baseline_scan(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消，未执行扫描", error_code="AGENT_TOOL_FAILED")

        from app.models.security import ProjectSnapshot

        snapshot = db.session.get(ProjectSnapshot, ctx.snapshot_id)
        if snapshot is None or not snapshot.storage_path:
            raise ToolExecutionError("快照存储路径缺失，无法扫描")
        root = Path(snapshot.storage_path).resolve()
        if not root.is_dir():
            raise ToolExecutionError("快照存储目录不存在")

        catalog_snapshot_files(snapshot)

        task = ScanTask(snapshot_id=ctx.snapshot_id, status=ScanTaskStatus.CREATED.value)
        db.session.add(task)
        db.session.flush()
        completed = run_scan_task(task.id)
        if completed.status.value if hasattr(completed.status, "value") else completed.status in {
            "completed",
            "completed_with_warnings",
        }:
            write_coverage_receipts_for_task(
                completed,
                root,
                exclusion_matcher=_task_exclusion_matcher(ctx),
            )
            db.session.commit()

        from app.models.security import SecurityFinding

        rows = SecurityFinding.query.filter_by(task_id=completed.id).all()
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in rows:
            severity = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
            counts[severity] = counts.get(severity, 0) + 1
        top = sorted(
            rows,
            key=lambda item: (
                SEVERITY_ORDER.get(item.severity.value if hasattr(item.severity, "value") else str(item.severity), 9),
                item.file_path,
            ),
        )[:10]
        languages = (completed.summary_json or {}).get("languages", [])
        summary = (
            f"扫描完成：{len(rows)} 个发现（高 {counts['high'] + counts['critical']}，"
            f"中 {counts['medium']}，低 {counts['low'] + counts['info']}），"
            f"语言 {', '.join(languages) if languages else '未识别'}"
        )
        return ToolResult(
            status="succeeded",
            summary=summary,
            artifact_refs=[
                {
                    "artifact_type": "finding_set",
                    "summary": f"task #{completed.id}: {len(rows)} findings",
                }
            ],
            metrics={
                "task_id": completed.id,
                "findings_count": len(rows),
                "severity_counts": counts,
                "languages": languages,
                "top_findings": [
                    {
                        "id": item.id,
                        "rule_id": item.rule_id,
                        "severity": item.severity.value if hasattr(item.severity, "value") else str(item.severity),
                        "file_path": item.file_path,
                        "start_line": item.start_line,
                        "message": item.message[:120],
                    }
                    for item in top
                ],
            },
        )

    return run_baseline_scan


def build_dependency_inventory_handler():
    def get_dependency_inventory(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消", error_code="AGENT_TOOL_FAILED")
        dependencies = SnapshotDependency.query.filter_by(snapshot_id=ctx.snapshot_id).all()
        ecosystems: dict[str, int] = {}
        for dependency in dependencies:
            ecosystems[dependency.ecosystem] = ecosystems.get(dependency.ecosystem, 0) + 1
        return ToolResult(
            status="succeeded",
            summary=f"依赖库存：{len(dependencies)} 个坐标，生态 {', '.join(ecosystems) or '无'}",
            metrics={
                "dependencies_count": len(dependencies),
                "ecosystems": ecosystems,
                "manifest_paths": sorted({d.manifest_path for d in dependencies})[:20],
            },
        )

    return get_dependency_inventory


def build_run_scanner_handler():
    """run_scanner: run a named subset of deterministic scanners on the snapshot.

    Industrial contract:
    - ``scanner_names`` is required and validated against the registered allowlist;
      unknown names fail with an explicit error, never a silent partial run.
    - The universal secret scanner is only run when explicitly requested.
    - A new ScanTask is created and executed through the real pipeline; findings
      and receipts are persisted idempotently, so re-runs do not duplicate rows.
    """
    registered = {descriptor.name: descriptor for descriptor in map(descriptor_for, get_scanners())}

    def run_scanner(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(
                status="failed", summary="任务已取消，未执行扫描", error_code="AGENT_TOOL_FAILED"
            )

        raw_names = ctx.input.get("scanner_names") or []
        if not isinstance(raw_names, list) or not raw_names:
            raise ToolExecutionError("scanner_names 必填，且必须是扫描器名称数组")
        names = []
        for item in raw_names:
            if not isinstance(item, str) or not item.strip():
                raise ToolExecutionError("scanner_names 只能包含非空字符串")
            names.append(item.strip())

        unknown = sorted(set(names) - set(registered) - {UNIVERSAL_SECRET_SCANNER_NAME})
        if unknown:
            allowed = sorted(registered) + [UNIVERSAL_SECRET_SCANNER_NAME]
            raise ToolExecutionError(
                f"未知扫描器：{', '.join(unknown)}；允许值：{', '.join(allowed)}",
                warning_code="AGENT_TOOL_INVALID_INPUT",
            )

        from app.models.security import ProjectSnapshot

        snapshot = db.session.get(ProjectSnapshot, ctx.snapshot_id)
        if snapshot is None or not snapshot.storage_path:
            raise ToolExecutionError("快照存储路径缺失，无法扫描")
        root = Path(snapshot.storage_path).resolve()
        if not root.is_dir():
            raise ToolExecutionError("快照存储目录不存在")

        catalog_snapshot_files(snapshot)

        task = ScanTask(snapshot_id=ctx.snapshot_id, status=ScanTaskStatus.CREATED.value)
        db.session.add(task)
        db.session.flush()

        selected = [
            scanner
            for scanner in get_scanners()
            if descriptor_for(scanner).name in names
        ]
        include_secret = UNIVERSAL_SECRET_SCANNER_NAME in names
        completed = run_scan_task(
            task.id,
            scanners=selected,
            include_universal_secret=include_secret,
        )
        if getattr(completed, "status", None) and (
            completed.status.value if hasattr(completed.status, "value") else completed.status
        ) not in {"completed", "completed_with_warnings"}:
            db.session.rollback()
            raise ToolExecutionError(
                f"扫描任务未完成：{completed.status}", warning_code="AGENT_TOOL_FAILED"
            )

        write_coverage_receipts_for_task(
            completed, root, exclusion_matcher=_task_exclusion_matcher(ctx)
        )
        db.session.commit()

        from app.models.security import SecurityFinding

        rows = SecurityFinding.query.filter_by(task_id=completed.id).all()
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in rows:
            severity = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
            counts[severity] = counts.get(severity, 0) + 1
        top = sorted(
            rows,
            key=lambda item: (
                SEVERITY_ORDER.get(
                    item.severity.value if hasattr(item.severity, "value") else str(item.severity), 9
                ),
                item.file_path,
            ),
        )[:10]
        summary = (
            f"定向扫描完成（{', '.join(names)}）：{len(rows)} 个发现"
            f"（高 {counts['high'] + counts['critical']}，"
            f"中 {counts['medium']}，低 {counts['low'] + counts['info']}）"
        )
        return ToolResult(
            status="succeeded",
            summary=summary,
            artifact_refs=[
                {
                    "artifact_type": "finding_set",
                    "summary": f"task #{completed.id}: {len(rows)} findings",
                }
            ],
            metrics={
                "task_id": completed.id,
                "scanner_names": names,
                "findings_count": len(rows),
                "severity_counts": counts,
                "top_findings": [
                    {
                        "id": item.id,
                        "rule_id": item.rule_id,
                        "severity": item.severity.value if hasattr(item.severity, "value") else str(item.severity),
                        "file_path": item.file_path,
                        "start_line": item.start_line,
                        "message": item.message[:120],
                    }
                    for item in top
                ],
            },
        )

    return run_scanner
