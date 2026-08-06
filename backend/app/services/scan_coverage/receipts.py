"""Idempotent per-file scan receipts for one scan task."""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.scan_coverage import CoverageKind, ScanFileReceipt
from app.models.security import ScanTask, SecurityFinding
from app.services.scan_coverage.classifier import detect_language, detect_text


def write_receipt(
    task: ScanTask,
    file_path: str,
    *,
    scanner_name: str,
    coverage_kind: CoverageKind | str,
    file_size: int = 0,
) -> None:
    """Insert one receipt row; unique (task, path, scanner, kind) keeps it idempotent."""
    kind = coverage_kind.value if isinstance(coverage_kind, CoverageKind) else str(coverage_kind)
    receipt = ScanFileReceipt(
        task_id=task.id,
        snapshot_id=task.snapshot_id,
        file_path=file_path,
        scanner_name=scanner_name,
        coverage_kind=kind,
        file_size=file_size,
    )
    db.session.add(receipt)


def write_coverage_receipts_for_task(
    task: ScanTask,
    snapshot_root: Path,
    *,
    exclusion_matcher=None,
) -> int:
    """Write one receipt per catalogued file for a completed scan task.

    Kind derivation:
      - excluded          : matched by project exclusion rules
      - baseline_scanned  : non-text/binary files (counted, not scannable)
      - scanned_with_findings / scanned_no_finding : text files scanned by the
        baseline (SAST + universal secret) pipeline, split by finding presence
      - specialized_sast  : text files with a dedicated language scanner
      - generic_only      : text files without a dedicated language scanner

    Returns the number of receipts written.
    """
    from app.models.scan_coverage import ProjectSnapshotFile

    finding_paths = {
        row[0]
        for row in SecurityFinding.query.filter_by(task_id=task.id)
        .with_entities(SecurityFinding.file_path)
        .distinct()
    }
    written = 0
    files = ProjectSnapshotFile.query.filter_by(snapshot_id=task.snapshot_id).all()
    existing_keys = {
        (row.file_path, row.scanner_name, _kind_value(row.coverage_kind))
        for row in ScanFileReceipt.query.filter_by(task_id=task.id).all()
    }
    for entry in files:
        excluded = exclusion_matcher is not None and exclusion_matcher.is_excluded(entry.file_path)
        if excluded:
            if _not_written(existing_keys, entry.file_path, "baseline", CoverageKind.EXCLUDED):
                write_receipt(
                    task,
                    entry.file_path,
                    scanner_name="baseline",
                    coverage_kind=CoverageKind.EXCLUDED,
                    file_size=entry.file_size,
                )
                written += 1
            continue
        if not entry.is_text:
            if _not_written(existing_keys, entry.file_path, "baseline", CoverageKind.BASELINE_SCANNED):
                write_receipt(
                    task,
                    entry.file_path,
                    scanner_name="baseline",
                    coverage_kind=CoverageKind.BASELINE_SCANNED,
                    file_size=entry.file_size,
                )
                written += 1
            continue
        specialized = entry.detected_language in {
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
        }
        if entry.file_path in finding_paths:
            kind = CoverageKind.SCANNED_WITH_FINDINGS
        else:
            kind = CoverageKind.SCANNED_NO_FINDING
        if _not_written(existing_keys, entry.file_path, "baseline", kind):
            write_receipt(
                task,
                entry.file_path,
                scanner_name="baseline",
                coverage_kind=kind,
                file_size=entry.file_size,
            )
            written += 1
        specialized_kind = CoverageKind.SPECIALIZED_SAST if specialized else CoverageKind.GENERIC_ONLY
        if _not_written(existing_keys, entry.file_path, "specialized_sast", specialized_kind):
            write_receipt(
                task,
                entry.file_path,
                scanner_name="specialized_sast",
                coverage_kind=specialized_kind,
                file_size=entry.file_size,
            )
            written += 1
    db.session.flush()
    return written


def _kind_value(kind) -> str:
    return kind.value if hasattr(kind, "value") else str(kind)


def _not_written(existing_keys: set, file_path: str, scanner_name: str, kind: CoverageKind) -> bool:
    return (file_path, scanner_name, _kind_value(kind)) not in existing_keys
