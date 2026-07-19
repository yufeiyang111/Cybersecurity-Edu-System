from pathlib import Path

from app import db
from app.models.security import ProjectSnapshot, ScanTask, ScanTaskStatus, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.scan_orchestrator import run_scan_task
from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding


def create_scan_task(tmp_path: Path, source: str) -> ScanTask:
    user = User(username="scanner", email="scanner@example.test", password_hash="x")
    workspace = Workspace(name="Scanner", slug="scanner")
    db.session.add_all([user, workspace])
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    project = SecurityProject(workspace_id=workspace.id, name="demo", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    snapshot_root = tmp_path / "snapshot"
    snapshot_root.mkdir()
    (snapshot_root / "danger.py").write_text(source, encoding="utf-8")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="a" * 64,
        storage_path=str(snapshot_root),
        file_count=1,
        total_bytes=len(source),
    )
    db.session.add(snapshot)
    db.session.flush()
    task = ScanTask(snapshot_id=snapshot.id, status="created", progress=0)
    db.session.add(task)
    db.session.commit()
    return task


def test_scan_task_persists_findings_and_completes(app, tmp_path):
    with app.app_context():
        task = create_scan_task(tmp_path, "import subprocess\nsubprocess.run(cmd, shell=True)\n")
        completed = run_scan_task(task.id)

        assert completed.status == ScanTaskStatus.COMPLETED.value
        assert completed.findings[0].rule_id == "PY-SHELL-TRUE"
        assert completed.findings[0].evidences[0].content_redacted
        assert completed.summary_json["findings_count"] == 1


class FailingScanner(BaseLanguageScanner):
    language = "failing"

    def can_handle(self, snapshot_root):
        return True

    def detect_project(self, snapshot_root):
        return ProjectProfile(language=self.language, framework_hints=[], manifest_paths=[])

    def run_sast(self, snapshot_root):
        raise RuntimeError("expected scanner failure")


def test_scanner_failure_preserves_completed_findings_as_warning(app, tmp_path, monkeypatch):
    with app.app_context():
        task = create_scan_task(tmp_path, "import subprocess\nsubprocess.run(cmd, shell=True)\n")
        from app.services.scanners.python_scanner import PythonScanner
        monkeypatch.setattr("app.services.scan_orchestrator.get_scanners", lambda: [PythonScanner(), FailingScanner()])

        completed = run_scan_task(task.id)

        assert completed.status == ScanTaskStatus.COMPLETED_WITH_WARNINGS.value
        assert completed.findings[0].rule_id == "PY-SHELL-TRUE"
        assert completed.summary_json["warnings"][0]["scanner"] == "failing"


def test_missing_snapshot_fails_without_traceback(app, tmp_path):
    with app.app_context():
        task = create_scan_task(tmp_path, "print('ok')\n")
        task.snapshot.storage_path = str(tmp_path / "does-not-exist")
        db.session.commit()

        completed = run_scan_task(task.id)

        assert completed.status == ScanTaskStatus.FAILED.value
        assert completed.error_code == "SNAPSHOT_NOT_FOUND"
        assert completed.to_dict()["has_error"] is True
