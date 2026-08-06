"""Coverage summaries: what was scanned, per task and per snapshot."""
from __future__ import annotations

from collections import Counter

from app import db
from app.models.scan_coverage import CoverageKind, ProjectSnapshotFile, ScanFileReceipt
from app.models.security import ScanTask


def coverage_summary(task: ScanTask) -> dict:
    """Aggregate receipt counts for one scan task into the coverage report."""
    rows = (
        ScanFileReceipt.query.filter_by(task_id=task.id)
        .with_entities(ScanFileReceipt.coverage_kind)
        .all()
    )
    counts: Counter = Counter()
    for (kind,) in rows:
        kind_value = kind.value if hasattr(kind, "value") else str(kind)
        counts[kind_value] += 1
    total_files = ProjectSnapshotFile.query.filter_by(snapshot_id=task.snapshot_id).count()
    findings_count = _findings_count(task.id)
    return {
        "task_id": task.id,
        "snapshot_id": task.snapshot_id,
        "total_files": total_files,
        "accounted_files": sum(counts.values()),
        "baseline_scanned": counts.get(CoverageKind.BASELINE_SCANNED.value, 0),
        "specialized_sast": counts.get(CoverageKind.SPECIALIZED_SAST.value, 0),
        "generic_only": counts.get(CoverageKind.GENERIC_ONLY.value, 0),
        "scanned_no_finding": counts.get(CoverageKind.SCANNED_NO_FINDING.value, 0),
        "scanned_with_findings": counts.get(CoverageKind.SCANNED_WITH_FINDINGS.value, 0),
        "excluded": counts.get(CoverageKind.EXCLUDED.value, 0),
        "skipped": counts.get(CoverageKind.SKIPPED.value, 0),
        "failed": counts.get(CoverageKind.FAILED.value, 0),
        "findings_count": findings_count,
    }


def list_coverage_files(
    task: ScanTask,
    *,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Paginated file receipts for one task, optionally filtered by coverage kind.

    Without a kind filter the baseline scanner's one-receipt-per-file view is
    returned; with a kind filter all matching receipts (any scanner) are shown.
    """
    if kind:
        query = ScanFileReceipt.query.filter_by(task_id=task.id, coverage_kind=kind)
    else:
        query = ScanFileReceipt.query.filter_by(task_id=task.id, scanner_name="baseline")
    total = query.count()
    page = (
        query.order_by(ScanFileReceipt.file_path.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [receipt.to_dict() for receipt in page], total


def _findings_count(task_id: int) -> int:
    from app.models.security import SecurityFinding

    return SecurityFinding.query.filter_by(task_id=task_id).count()
