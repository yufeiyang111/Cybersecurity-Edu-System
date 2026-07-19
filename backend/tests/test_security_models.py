import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.security import (
    AuditEvent,
    FindingEvidence,
    ProjectSnapshot,
    ScanTask,
    SecurityFinding,
    SecurityProject,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User


def make_task():
    user = User(username="alice", email="alice@example.test", password_hash="x")
    workspace = Workspace(name="Alice", slug="alice")
    db.session.add_all([user, workspace])
    db.session.flush()

    db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    project = SecurityProject(workspace_id=workspace.id, name="demo", created_by=user.id)
    db.session.add(project)
    db.session.flush()

    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="a" * 64,
        file_count=1,
        total_bytes=1,
    )
    db.session.add(snapshot)
    db.session.flush()

    task = ScanTask(snapshot_id=snapshot.id, status="created", progress=0)
    db.session.add(task)
    db.session.flush()
    return workspace, user, task


def test_workspace_membership_is_unique(app):
    with app.app_context():
        workspace, user, _ = make_task()
        db.session.commit()

        assert workspace.members[0].role == "owner"
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="viewer"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_finding_fingerprint_is_unique_per_task(app):
    with app.app_context():
        _, _, task = make_task()
        db.session.add(
            SecurityFinding(
                task_id=task.id,
                fingerprint="same",
                rule_id="PY-SHELL-TRUE",
                category="sast",
                severity="high",
                file_path="a.py",
                start_line=1,
                message="x",
            )
        )
        db.session.commit()

        db.session.add(
            SecurityFinding(
                task_id=task.id,
                fingerprint="same",
                rule_id="PY-SHELL-TRUE",
                category="sast",
                severity="high",
                file_path="a.py",
                start_line=1,
                message="x",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_finding_and_evidence_serialization_redacts_secret_values(app):
    with app.app_context():
        _, user, task = make_task()
        finding = SecurityFinding(
            task_id=task.id,
            fingerprint="secret-finding",
            rule_id="SECRET-AWS-ACCESS-KEY",
            category="secret",
            severity="critical",
            file_path="settings.py",
            start_line=8,
            message="Potential credential found",
        )
        db.session.add(finding)
        db.session.flush()
        evidence = FindingEvidence(
            finding_id=finding.id,
            evidence_type="secret",
            content_redacted="AKIA***WXYZ",
            secret_hash="sha256:abc",
            source_uri="settings.py",
            start_line=8,
            end_line=8,
        )
        db.session.add_all(
            [
                evidence,
                AuditEvent(
                    workspace_id=user.workspace_memberships[0].workspace_id,
                    actor_id=user.id,
                    action="finding.viewed",
                    target_type="security_finding",
                    target_id=finding.id,
                ),
            ]
        )
        db.session.commit()

        finding_data = finding.to_dict()
        evidence_data = evidence.to_dict()

        assert finding_data["status"] == "open"
        assert finding_data["severity"] == "critical"
        assert evidence_data["content"] == "AKIA***WXYZ"
        assert "secret_hash" not in evidence_data
        assert "raw_secret" not in finding_data
