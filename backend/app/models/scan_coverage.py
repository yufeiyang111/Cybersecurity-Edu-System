"""Persistence models for scan coverage: snapshot file catalog and receipts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class CoverageKind(str, Enum):
    ACCOUNTED = "accounted"
    BASELINE_SCANNED = "baseline_scanned"
    SPECIALIZED_SAST = "specialized_sast"
    GENERIC_ONLY = "generic_only"
    SCANNED_NO_FINDING = "scanned_no_finding"
    SCANNED_WITH_FINDINGS = "scanned_with_findings"
    EXCLUDED = "excluded"
    SKIPPED = "skipped"
    FAILED = "failed"


class ProjectSnapshotFile(db.Model):
    """Immutable per-snapshot file catalog entry (metadata only, never content)."""

    __tablename__ = "project_snapshot_files"
    __table_args__ = (
        db.UniqueConstraint("snapshot_id", "file_path", name="uq_snapshot_files_path"),
        db.Index("ix_snapshot_files_snapshot_text", "snapshot_id", "is_text"),
    )

    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(
        db.Integer, db.ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    extension = db.Column(db.String(64))
    is_text = db.Column(db.Boolean, nullable=False, default=False)
    detected_language = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    snapshot = db.relationship("ProjectSnapshot")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "snapshot_id": self.snapshot_id,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "extension": self.extension,
            "is_text": bool(self.is_text),
            "detected_language": self.detected_language,
        }


class ScanFileReceipt(db.Model):
    """Idempotent per-file per-scanner scan outcome receipt."""

    __tablename__ = "scan_file_receipts"
    __table_args__ = (
        db.UniqueConstraint(
            "task_id",
            "file_path",
            "scanner_name",
            "coverage_kind",
            name="uq_scan_receipts_scope",
        ),
        db.Index("ix_scan_receipts_task_status", "task_id", "coverage_kind"),
        db.Index("ix_scan_receipts_snapshot", "snapshot_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer, db.ForeignKey("scan_tasks.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id = db.Column(
        db.Integer, db.ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    file_path = db.Column(db.String(512), nullable=False)
    scanner_name = db.Column(db.String(128), nullable=False)
    coverage_kind = db.Column(
        db.Enum(CoverageKind, name="scan_coverage_kind", values_callable=_enum_values),
        nullable=False,
        default=CoverageKind.ACCOUNTED.value,
    )
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    task = db.relationship("ScanTask")
    snapshot = db.relationship("ProjectSnapshot")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "snapshot_id": self.snapshot_id,
            "file_path": self.file_path,
            "scanner_name": self.scanner_name,
            "coverage_kind": self.coverage_kind.value
            if isinstance(self.coverage_kind, Enum)
            else self.coverage_kind,
            "file_size": self.file_size,
        }
