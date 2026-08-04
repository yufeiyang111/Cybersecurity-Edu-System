"""应用层扫描编排入口。

扫描只对已经安全落盘的不可变快照做确定性静态分析；不执行被扫描项目代码。
"""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.security import ScanTask, ScanTaskStatus
from app.services.scan_execution import execute_scan_stages, execute_universal_secret_scan
from app.services.osv_client import OSVVulnerabilityProvider
from app.services.scan_task_lifecycle import (
    TERMINAL_STATUSES,
    ScanTaskStateError,
    cancel_scan_task,
    claim_scan_task,
    is_terminal_status,
    record_task_audit,
    status_value,
    transition_task,
)
from app.services.scanners import get_scanners


# 兼容既有内部调用；新增代码应使用 scan_task_lifecycle 中的语义化名称。
_value = status_value
_transition = transition_task


def run_scan_task(task_id: int) -> ScanTask:
    """执行已持久化快照的确定性扫描，不执行任何源代码。"""
    task = db.session.get(ScanTask, task_id)
    if task is None:
        raise ValueError("扫描任务不存在")
    if is_terminal_status(task.status):
        return task

    claimed_task = claim_scan_task(task_id)
    if claimed_task is None:
        return db.session.get(ScanTask, task_id) or task
    task = claimed_task

    try:
        transition_task(task, ScanTaskStatus.VALIDATING.value, 10)
        snapshot_root = Path(task.snapshot.storage_path or "").resolve()
        if not snapshot_root.is_dir():
            task.error_code = "SNAPSHOT_NOT_FOUND"
            transition_task(task, ScanTaskStatus.FAILED.value, 100)
            record_task_audit(task, "scan.failed", {"error_code": task.error_code})
            db.session.commit()
            return task

        transition_task(task, ScanTaskStatus.SNAPSHOTTING.value, 25)
        transition_task(task, ScanTaskStatus.SCANNING.value, 40)
        execution = execute_scan_stages(
            task,
            snapshot_root,
            scanners=get_scanners(),
            vulnerability_provider=OSVVulnerabilityProvider(),
        )
        secret_findings = execute_universal_secret_scan(task, snapshot_root)
        task.summary_json = {
            "findings_count": execution.findings_count,
            "languages": execution.languages,
            "dependencies_count": execution.dependencies_count,
            "sca_findings_count": execution.sca_findings_count,
            "sca_enabled": execution.sca_enabled,
            "secret_findings_count": secret_findings,
            "warnings": execution.warnings,
        }
        if execution.completed_scanners:
            final_status = (
                ScanTaskStatus.COMPLETED_WITH_WARNINGS.value
                if execution.warnings
                else ScanTaskStatus.COMPLETED.value
            )
            transition_task(task, final_status, 100)
            record_task_audit(task, "scan.completed", {"warnings_count": len(execution.warnings)})
        else:
            task.error_code = "NO_SCANNER_COMPLETED"
            transition_task(task, ScanTaskStatus.FAILED.value, 100)
            record_task_audit(
                task,
                "scan.failed",
                {"error_code": task.error_code, "warnings": execution.warnings},
            )
        db.session.commit()
        return task
    except Exception:
        db.session.rollback()
        task = db.session.get(ScanTask, task_id)
        if task is None:
            raise
        if not is_terminal_status(task.status):
            task.error_code = "SCAN_ORCHESTRATION_ERROR"
            transition_task(task, ScanTaskStatus.FAILED.value, 100)
            record_task_audit(task, "scan.failed", {"error_code": task.error_code})
            db.session.commit()
        return task


def run_queued_scan_task(task_id: int) -> ScanTask:
    """RQ Worker 入口：在独立进程内创建 Flask application context。"""
    from app import create_app

    application = create_app()
    with application.app_context():
        return run_scan_task(task_id)


__all__ = [
    "TERMINAL_STATUSES",
    "ScanTaskStateError",
    "cancel_scan_task",
    "run_queued_scan_task",
    "run_scan_task",
]
