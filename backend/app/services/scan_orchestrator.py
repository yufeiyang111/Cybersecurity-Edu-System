"""Persistent state machine for read-only security scans."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from app import db
from app.models.security import (
    AuditEvent,
    FindingEvidence,
    ScanTask,
    ScanTaskStatus,
    SecurityFinding,
)
from app.services.scanners import get_scanners
from app.services.scanners.base import RawFinding


TERMINAL_STATUSES = {
    ScanTaskStatus.COMPLETED.value,
    ScanTaskStatus.COMPLETED_WITH_WARNINGS.value,
    ScanTaskStatus.FAILED.value,
    ScanTaskStatus.CANCELED.value,
}
ALLOWED_TRANSITIONS = {
    ScanTaskStatus.CREATED.value: {ScanTaskStatus.VALIDATING.value, ScanTaskStatus.CANCELED.value},
    ScanTaskStatus.VALIDATING.value: {ScanTaskStatus.SNAPSHOTTING.value, ScanTaskStatus.FAILED.value, ScanTaskStatus.CANCELED.value},
    ScanTaskStatus.SNAPSHOTTING.value: {ScanTaskStatus.SCANNING.value, ScanTaskStatus.FAILED.value, ScanTaskStatus.CANCELED.value},
    ScanTaskStatus.SCANNING.value: {ScanTaskStatus.COMPLETED.value, ScanTaskStatus.COMPLETED_WITH_WARNINGS.value, ScanTaskStatus.FAILED.value, ScanTaskStatus.CANCELED.value},
    ScanTaskStatus.COMPLETED.value: set(),
    ScanTaskStatus.COMPLETED_WITH_WARNINGS.value: set(),
    ScanTaskStatus.FAILED.value: set(),
    ScanTaskStatus.CANCELED.value: set(),
}


class ScanTaskStateError(ValueError):
    """Raised when a task attempts an illegal state transition."""


def _value(value: object) -> str:
    return getattr(value, "value", value)


def _transition(task: ScanTask, status: str, progress: int) -> None:
    current = _value(task.status)
    if status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ScanTaskStateError(f"非法扫描任务状态流转: {current} -> {status}")
    task.status = status
    task.progress = progress
    if status == ScanTaskStatus.SCANNING.value and task.started_at is None:
        task.started_at = datetime.utcnow()
    if status in TERMINAL_STATUSES:
        task.finished_at = datetime.utcnow()
    db.session.flush()


def cancel_scan_task(task: ScanTask) -> None:
    """Cancel a non-terminal scan task without removing its persisted evidence."""
    current = _value(task.status)
    if current in TERMINAL_STATUSES:
        raise ScanTaskStateError("已结束的扫描任务不能取消")
    _transition(task, ScanTaskStatus.CANCELED.value, task.progress)
    task.canceled_at = datetime.utcnow()
    task.error_code = None
    db.session.commit()


def _finding_fingerprint(finding: RawFinding) -> str:
    evidence_digest = sha256(finding.evidence_preview.encode("utf-8")).hexdigest()
    canonical = f"{finding.rule_id}:{finding.file_path}:{finding.start_line}:{evidence_digest}"
    return sha256(canonical.encode("utf-8")).hexdigest()


def _persist_finding(task: ScanTask, finding: RawFinding) -> SecurityFinding:
    fingerprint = _finding_fingerprint(finding)
    persisted = SecurityFinding.query.filter_by(task_id=task.id, fingerprint=fingerprint).one_or_none()
    if persisted is None:
        persisted = SecurityFinding(
            task_id=task.id,
            fingerprint=fingerprint,
            rule_id=finding.rule_id,
            category=finding.category,
            severity=finding.severity,
            cwe_id=finding.cwe_id,
            file_path=finding.file_path,
            start_line=finding.start_line,
            end_line=finding.end_line,
            message=finding.message,
            confidence=1.0,
            rule_version="python-baseline-v1",
        )
        db.session.add(persisted)
        db.session.flush()

    evidence_exists = FindingEvidence.query.filter_by(
        finding_id=persisted.id,
        evidence_type="secret" if finding.secret_sha256 else "code",
        source_uri=finding.file_path,
        start_line=finding.start_line,
        end_line=finding.end_line,
    ).one_or_none()
    if evidence_exists is None:
        db.session.add(
            FindingEvidence(
                finding_id=persisted.id,
                evidence_type="secret" if finding.secret_sha256 else "code",
                content_redacted=finding.evidence_preview,
                secret_hash=finding.secret_sha256,
                source_uri=finding.file_path,
                start_line=finding.start_line,
                end_line=finding.end_line,
                score=1.0,
            )
        )
    return persisted


def _all_findings(scanner: object, snapshot_root: Path) -> Iterable[RawFinding]:
    yield from scanner.run_sast(snapshot_root)
    yield from scanner.run_secret_scan(snapshot_root)


def _record_audit(task: ScanTask, action: str, metadata: dict) -> None:
    workspace_id = task.snapshot.project.workspace_id
    db.session.add(
        AuditEvent(
            workspace_id=workspace_id,
            action=action,
            target_type="scan_task",
            target_id=task.id,
            metadata_json=metadata,
        )
    )


def run_scan_task(task_id: int) -> ScanTask:
    """Run deterministic scans for a persisted snapshot; no source is executed."""
    task = db.session.get(ScanTask, task_id)
    if task is None:
        raise ValueError("扫描任务不存在")
    if _value(task.status) in TERMINAL_STATUSES:
        return task

    warnings: list[dict[str, str]] = []
    completed_scanners = 0
    try:
        _transition(task, ScanTaskStatus.VALIDATING.value, 10)
        snapshot_root = Path(task.snapshot.storage_path or "").resolve()
        if not snapshot_root.is_dir():
            task.error_code = "SNAPSHOT_NOT_FOUND"
            _transition(task, ScanTaskStatus.FAILED.value, 100)
            _record_audit(task, "scan.failed", {"error_code": task.error_code})
            db.session.commit()
            return task

        _transition(task, ScanTaskStatus.SNAPSHOTTING.value, 25)
        _transition(task, ScanTaskStatus.SCANNING.value, 40)
        for scanner in get_scanners():
            if _value(task.status) == ScanTaskStatus.CANCELED.value:
                db.session.commit()
                return task
            if not scanner.can_handle(snapshot_root):
                continue
            try:
                scanner.detect_project(snapshot_root)
                for finding in _all_findings(scanner, snapshot_root):
                    _persist_finding(task, finding)
                completed_scanners += 1
            except Exception as exc:  # scanner failures are isolated and never expose source text
                warnings.append({"scanner": getattr(scanner, "language", scanner.__class__.__name__), "error": type(exc).__name__})

        task.summary_json = {
            "findings_count": SecurityFinding.query.filter_by(task_id=task.id).count(),
            "warnings": warnings,
        }
        if completed_scanners:
            final_status = (
                ScanTaskStatus.COMPLETED_WITH_WARNINGS.value if warnings else ScanTaskStatus.COMPLETED.value
            )
            _transition(task, final_status, 100)
            _record_audit(task, "scan.completed", {"warnings_count": len(warnings)})
        else:
            task.error_code = "NO_SCANNER_COMPLETED"
            _transition(task, ScanTaskStatus.FAILED.value, 100)
            _record_audit(task, "scan.failed", {"error_code": task.error_code, "warnings": warnings})
        db.session.commit()
        return task
    except Exception:
        db.session.rollback()
        task = db.session.get(ScanTask, task_id)
        if task is None:
            raise
        if _value(task.status) not in TERMINAL_STATUSES:
            task.error_code = "SCAN_ORCHESTRATION_ERROR"
            _transition(task, ScanTaskStatus.FAILED.value, 100)
            _record_audit(task, "scan.failed", {"error_code": task.error_code})
            db.session.commit()
        return task


def run_queued_scan_task(task_id: int) -> ScanTask:
    """RQ entrypoint that creates the Flask application context in the worker process."""
    from app import create_app

    application = create_app()
    with application.app_context():
        return run_scan_task(task_id)
