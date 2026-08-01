from __future__ import annotations

from pathlib import Path

from app import db
from app.models.security import ProjectSnapshot, ScanTask, ScanTaskStatus, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.scan_task_lifecycle import (
    ScanTaskStateError,
    cancel_scan_task,
    claim_scan_task,
    mark_dispatch_failed,
    prepare_scan_task_retry,
)


def _task(tmp_path: Path) -> ScanTask:
    user = User(username="lifecycle", email="lifecycle@example.test", password_hash="x")
    workspace = Workspace(name="Lifecycle", slug="lifecycle")
    db.session.add_all([user, workspace])
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    project = SecurityProject(workspace_id=workspace.id, name="lifecycle", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    snapshot_root = tmp_path / "snapshot"
    snapshot_root.mkdir()
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="b" * 64,
        storage_path=str(snapshot_root),
        file_count=0,
        total_bytes=0,
    )
    db.session.add(snapshot)
    db.session.flush()
    task = ScanTask(snapshot_id=snapshot.id, status="created", dispatch_key="dispatch-1")
    db.session.add(task)
    db.session.commit()
    return task


def test_claim_scan_task_is_single_worker_and_idempotent(app, tmp_path):
    with app.app_context():
        task = _task(tmp_path)

        first = claim_scan_task(task.id, worker_id="worker-a")
        second = claim_scan_task(task.id, worker_id="worker-b")

        assert first is not None
        assert first.worker_id == "worker-a"
        assert second is None


def test_cancel_scan_task_records_audit_and_rejects_terminal_task(app, tmp_path):
    with app.app_context():
        task = _task(tmp_path)
        cancel_scan_task(task, actor_id=None)

        assert task.status == ScanTaskStatus.CANCELED.value
        assert task.canceled_at is not None
        try:
            cancel_scan_task(task)
        except ScanTaskStateError as exc:
            assert "不能取消" in str(exc)
        else:
            raise AssertionError("terminal task cancellation should fail")


def test_prepare_scan_task_retry_resets_failure_and_increments_counter(app, tmp_path):
    with app.app_context():
        task = _task(tmp_path)
        task.status = ScanTaskStatus.FAILED.value
        task.progress = 100
        task.error_code = "SCAN_DISPATCH_FAILED"
        task.dispatch_key = "old-dispatch"
        db.session.commit()

        retried = prepare_scan_task_retry(task)

        assert retried.status == ScanTaskStatus.CREATED.value
        assert retried.progress == 0
        assert retried.retry_count == 1
        assert retried.error_code is None
        assert retried.dispatch_key != "old-dispatch"

def test_retry_limit_and_dispatch_failure_are_safe(app, tmp_path):
    with app.app_context():
        task = _task(tmp_path)
        task.status = ScanTaskStatus.FAILED.value
        task.retry_count = 3
        db.session.commit()

        try:
            prepare_scan_task_retry(task, max_retries=3)
        except ScanTaskStateError as exc:
            assert "最大重试次数" in str(exc)
        else:
            raise AssertionError("retry limit should be enforced")

        task.status = ScanTaskStatus.CREATED.value
        db.session.commit()
        failed = mark_dispatch_failed(task.id)
        assert failed.status == ScanTaskStatus.FAILED.value
        assert failed.error_code == "SCAN_DISPATCH_FAILED"
        assert failed.error_message is None