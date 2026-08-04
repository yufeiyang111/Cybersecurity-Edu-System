"""Snapshot file catalog tests: metadata-only inventory, idempotent."""
from __future__ import annotations

from app import db
from app.models.scan_coverage import ProjectSnapshotFile
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.scan_coverage.catalog import catalog_snapshot_files
from app.services.workspaces import get_or_create_personal_workspace


def _make_snapshot(app, tmp_path, name="catalog") -> int:
    with app.app_context():
        user = User(username=name, email=f"{name}@t", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = get_or_create_personal_workspace(user.id)
        project = SecurityProject(workspace_id=workspace.id, name=name, created_by=user.id)
        db.session.add(project)
        db.session.flush()
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        (root / "app.py").write_text("x = 1\n", encoding="utf-8")
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "app.yml").write_text("debug: true\n", encoding="utf-8")
        (root / "logo.png").write_bytes(b"\x89PNG\x00\x01")
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="abc",
            storage_path=str(root),
            file_count=3,
            total_bytes=20,
        )
        db.session.add(snapshot)
        db.session.commit()
        return snapshot.id


def test_catalog_populates_metadata(app, tmp_path):
    snapshot_id = _make_snapshot(app, tmp_path)
    with app.app_context():
        snapshot = db.session.get(ProjectSnapshot, snapshot_id)
        count = catalog_snapshot_files(snapshot)
        assert count == 3
        entries = {
            row.file_path: row
            for row in ProjectSnapshotFile.query.filter_by(snapshot_id=snapshot_id).all()
        }
        assert entries["app.py"].is_text is True
        assert entries["app.py"].detected_language == "python"
        assert entries["config/app.yml"].is_text is True
        assert entries["config/app.yml"].detected_language == "config"
        assert entries["logo.png"].is_text is False


def test_catalog_is_idempotent(app, tmp_path):
    snapshot_id = _make_snapshot(app, tmp_path)
    with app.app_context():
        snapshot = db.session.get(ProjectSnapshot, snapshot_id)
        catalog_snapshot_files(snapshot)
        catalog_snapshot_files(snapshot)
        assert ProjectSnapshotFile.query.filter_by(snapshot_id=snapshot_id).count() == 3
