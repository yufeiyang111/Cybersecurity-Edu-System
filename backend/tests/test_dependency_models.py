from __future__ import annotations

from datetime import datetime
import json

import pytest
from flask import Config as FlaskConfig
from sqlalchemy.exc import IntegrityError

from app import db
from app.config import Config
from app.models import security
from app.models.user import User
from app.services.dependency_scanner import DependencyCoordinate, dependency_coordinate_hash


def _coordinate_hash(ecosystem: str, package_name: str, version: str, manifest_path: str) -> str:
    return dependency_coordinate_hash(
        DependencyCoordinate(ecosystem, package_name, version, manifest_path, True, None)
    )


def _make_snapshot():
    user = User(
        username="dependency-alice",
        email="dependency-alice@example.test",
        password_hash="x",
    )
    workspace = security.Workspace(
        name="Dependency workspace", slug="dependency-workspace"
    )
    db.session.add_all([user, workspace])
    db.session.flush()

    db.session.add(
        security.WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
    )
    project = security.SecurityProject(
        workspace_id=workspace.id,
        name="dependency-project",
        created_by=user.id,
    )
    db.session.add(project)
    db.session.flush()

    snapshot = security.ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="d" * 64,
        file_count=1,
        total_bytes=1,
    )
    db.session.add(snapshot)
    db.session.flush()
    return snapshot


def test_snapshot_dependency_is_unique_per_snapshot(app):
    with app.app_context():
        snapshot = _make_snapshot()
        dependency = security.SnapshotDependency(
            snapshot_id=snapshot.id,
            ecosystem="PyPI",
            package_name="requests",
            version="2.32.3",
            manifest_path="requirements.txt",
            coordinate_hash=_coordinate_hash("PyPI", "requests", "2.32.3", "requirements.txt"),
            is_direct=True,
            source_line=1,
        )
        db.session.add(dependency)
        db.session.commit()

        assert snapshot.dependencies == [dependency]

        db.session.add(
            security.SnapshotDependency(
                snapshot_id=snapshot.id,
                ecosystem="PyPI",
                package_name="requests",
                version="2.32.3",
                manifest_path="requirements.txt",
                coordinate_hash=_coordinate_hash("PyPI", "requests", "2.32.3", "requirements.txt"),
                is_direct=False,
                source_line=9,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_dependency_and_advisory_cache_serialization_are_safe(app):
    with app.app_context():
        snapshot = _make_snapshot()
        dependency = security.SnapshotDependency(
            snapshot_id=snapshot.id,
            ecosystem="npm",
            package_name="@acme/widget",
            version="1.2.3",
            manifest_path="package-lock.json",
            coordinate_hash=_coordinate_hash("npm", "@acme/widget", "1.2.3", "package-lock.json"),
            is_direct=False,
            source_line=24,
        )
        advisory = security.VulnerabilityAdvisoryCache(
            cache_key="osv:" + "a" * 64,
            ecosystem="npm",
            package_name="@acme/widget",
            version="1.2.3",
            response_json={
                "vulns": [{"id": "GHSA-test", "private_note": "must-not-leak"}]
            },
            fetched_at=datetime(2026, 7, 19, 0, 0, 0),
            expires_at=datetime(2026, 7, 20, 0, 0, 0),
        )
        db.session.add_all([dependency, advisory])
        db.session.commit()

        dependency_data = dependency.to_dict()
        advisory_data = advisory.to_dict()

        assert dependency_data == {
            "id": dependency.id,
            "snapshot_id": snapshot.id,
            "ecosystem": "npm",
            "package_name": "@acme/widget",
            "version": "1.2.3",
            "manifest_path": "package-lock.json",
            "is_direct": False,
            "source_line": 24,
        }
        assert advisory_data["cache_key"] == advisory.cache_key
        assert advisory_data["coordinate"] == {
            "ecosystem": "npm",
            "package_name": "@acme/widget",
            "version": "1.2.3",
        }
        assert advisory_data["has_cached_response"] is True
        assert "response_json" not in advisory_data
        assert "must-not-leak" not in json.dumps(advisory_data)


def test_phase_two_config_validation_accepts_flask_mapping_and_rejects_unsafe_values():
    settings = FlaskConfig("dependency-config")
    settings.update(
        {
            "APP_ENV": "testing",
            "CORS_ALLOWED_ORIGINS": ["https://security.example.test"],
            "SECURITY_WORKSPACE_ROOT": "security-workspaces",
            "RQ_QUEUE_NAME": "cyberguard-security-test",
            "RQ_ASYNC": False,
            "ARCHIVE_MAX_UPLOAD_BYTES": 50 * 1024 * 1024,
            "ARCHIVE_MAX_EXTRACT_BYTES": 500 * 1024 * 1024,
            "ARCHIVE_MAX_FILES": 20_000,
            "ARCHIVE_MAX_DEPTH": 10,
            "GITHUB_API_TIMEOUT_SECONDS": 15,
            "GITHUB_MAX_REDIRECTS": 1,
            "SCA_OSV_ENABLED": False,
            "SCA_OSV_API_URL": "https://api.osv.dev/v1/querybatch",
            "SCA_REQUEST_TIMEOUT_SECONDS": 15,
            "SCA_CACHE_TTL_SECONDS": 86_400,
            "SCA_MAX_DEPENDENCIES": 10_000,
        }
    )

    Config.validate_security_settings(settings)

    settings["SCA_OSV_API_URL"] = "http://api.osv.dev/v1/querybatch"
    with pytest.raises(ValueError, match="SCA_OSV_API_URL"):
        Config.validate_security_settings(settings)

    settings["SCA_OSV_API_URL"] = "https://api.osv.dev/v1/querybatch"
    settings["SCA_MAX_DEPENDENCIES"] = 1_000_000
    with pytest.raises(ValueError, match="SCA_MAX_DEPENDENCIES"):
        Config.validate_security_settings(settings)

    settings["SCA_MAX_DEPENDENCIES"] = 10_000
    settings["GITHUB_MAX_REDIRECTS"] = 2
    with pytest.raises(ValueError, match="GITHUB_MAX_REDIRECTS"):
        Config.validate_security_settings(settings)


def test_phase_two_dependency_indexes_are_safe_for_mysql_utf8mb4():
    dependency_columns = security.SnapshotDependency.__table__.columns
    assert "coordinate_hash" in dependency_columns

    unique_constraint_columns = {
        tuple(constraint.columns.keys())
        for constraint in security.SnapshotDependency.__table__.constraints
        if getattr(constraint, "unique", False) or constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("snapshot_id", "coordinate_hash") in unique_constraint_columns
    assert ("snapshot_id", "ecosystem", "package_name", "version", "manifest_path") not in unique_constraint_columns

    dependency_indexes = {index.name: tuple(index.columns.keys()) for index in security.SnapshotDependency.__table__.indexes}
    advisory_indexes = {index.name: tuple(index.columns.keys()) for index in security.VulnerabilityAdvisoryCache.__table__.indexes}
    assert dependency_indexes["ix_snapshot_dependencies_coordinate_hash"] == ("coordinate_hash",)
    assert "ix_vulnerability_advisory_cache_coordinate" not in advisory_indexes

    repository_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    migration_sql = (repository_root / "database" / "migrations" / "002_github_multilang_sca.sql").read_text(encoding="utf-8")
    init_sql = (repository_root / "database" / "init.sql").read_text(encoding="utf-8")
    for sql in (migration_sql, init_sql):
        assert "coordinate_hash VARCHAR(64) NOT NULL" in sql
        assert "snapshot_id, coordinate_hash" in sql
        assert "ix_snapshot_dependencies_coordinate_hash (coordinate_hash)" in sql
        assert "ix_vulnerability_advisory_cache_coordinate" not in sql
