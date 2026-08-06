"""Immutable snapshot file catalog: metadata-only inventory, never content."""
from __future__ import annotations

from pathlib import Path

from app import db
from app.models.scan_coverage import ProjectSnapshotFile
from app.models.security import ProjectSnapshot
from app.services.scan_coverage.classifier import detect_language, detect_text


def catalog_snapshot_files(snapshot: ProjectSnapshot) -> int:
    """Populate project_snapshot_files for a snapshot (idempotent by snapshot+path).

    Returns the number of catalog entries after this call.
    """
    root = Path(snapshot.storage_path or "").resolve()
    if not root.is_dir():
        return _catalog_count(snapshot.id)

    batch: list[ProjectSnapshotFile] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith("__pycache__/") or "/.git/" in f"/{relative}":
            continue
        suffix = path.suffix.lower()
        is_text = detect_text(path)
        batch.append(
            ProjectSnapshotFile(
                snapshot_id=snapshot.id,
                file_path=relative,
                file_size=path.stat().st_size,
                extension=suffix or None,
                is_text=is_text,
                detected_language=detect_language(suffix),
            )
        )
        if len(batch) >= 500:
            _flush_batch(snapshot.id, batch)
            batch = []
    _flush_batch(snapshot.id, batch)
    return _catalog_count(snapshot.id)


def _flush_batch(snapshot_id: int, batch: list[ProjectSnapshotFile]) -> None:
    if not batch:
        return
    existing = {
        (row.file_path,)
        for row in ProjectSnapshotFile.query.filter_by(snapshot_id=snapshot_id).with_entities(
            ProjectSnapshotFile.file_path
        )
    }
    fresh = [entry for entry in batch if (entry.file_path,) not in existing]
    if fresh:
        db.session.add_all(fresh)
        db.session.flush()


def _catalog_count(snapshot_id: int) -> int:
    return ProjectSnapshotFile.query.filter_by(snapshot_id=snapshot_id).count()
