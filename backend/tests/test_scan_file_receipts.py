"""Scan receipt and coverage summary tests."""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.scan_coverage import CoverageKind, ProjectSnapshotFile, ScanFileReceipt
from app.models.security import (
    ProjectSnapshot,
    ScanTask,
    SecurityFinding,
    SecurityProject,
)
from app.models.user import User
from app.services.scan_coverage.catalog import catalog_snapshot_files
from app.services.scan_coverage.receipts import write_coverage_receipts_for_task
from app.services.scan_coverage.summary import coverage_summary, list_coverage_files
from app.services.workspaces import get_or_create_personal_workspace


def _make_task_with_findings(app, tmp_path) -> tuple[ScanTask, Path]:
    user = User(username="receipt", email="receipt@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = get_or_create_personal_workspace(user.id)
    project = SecurityProject(workspace_id=workspace.id, name="receipt", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text("import os\n", encoding="utf-8")
    legacy_dir = root / "legacy"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "old.php").write_text("<?php echo 1;\n", encoding="utf-8")
    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "logo.png").write_bytes(b"\x89PNG\x00")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="abc",
        storage_path=str(root),
        file_count=3,
        total_bytes=20,
    )
    db.session.add(snapshot)
    db.session.flush()
    catalog_snapshot_files(snapshot)
    task = ScanTask(snapshot_id=snapshot.id, status="completed")
    db.session.add(task)
    db.session.flush()
    finding = SecurityFinding(
        task_id=task.id,
        fingerprint="f1",
        rule_id="PY-OS-1",
        category="sast",
        severity="high",
        file_path="app.py",
        start_line=1,
        end_line=1,
        message="danger",
    )
    db.session.add(finding)
    db.session.commit()
    return task, root


def test_receipts_cover_every_file_without_duplicates(app, tmp_path):
    with app.app_context():
        task, root = _make_task_with_findings(app, tmp_path)
        first = write_coverage_receipts_for_task(task, root)
        second = write_coverage_receipts_for_task(task, root)
        db.session.commit()
        assert first > 0
        assert second == 0, "重复写收据必须幂等"
        rows = ScanFileReceipt.query.filter_by(task_id=task.id).all()
        assert len(rows) == first


def test_coverage_summary_counts_kinds(app, tmp_path):
    with app.app_context():
        task, root = _make_task_with_findings(app, tmp_path)
        write_coverage_receipts_for_task(task, root)
        db.session.commit()
        summary = coverage_summary(task)
        assert summary["total_files"] == 3
        assert summary["scanned_with_findings"] == 1
        assert summary["scanned_no_finding"] == 1
        assert summary["baseline_scanned"] == 1
        assert summary["specialized_sast"] == 1
        assert summary["generic_only"] == 1
        assert summary["findings_count"] == 1


def test_list_coverage_files_filters_by_kind(app, tmp_path):
    with app.app_context():
        task, root = _make_task_with_findings(app, tmp_path)
        write_coverage_receipts_for_task(task, root)
        db.session.commit()
        files, total = list_coverage_files(task, kind=CoverageKind.SCANNED_WITH_FINDINGS.value)
        assert total == 1
        assert files[0]["file_path"] == "app.py"
        files, total = list_coverage_files(task)
        assert total == 3
