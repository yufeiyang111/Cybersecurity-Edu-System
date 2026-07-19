"""Workspace-scoped project and scan APIs."""
from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.datastructures import FileStorage

from app import db
from app.models.security import AuditEvent, ProjectSnapshot, ScanTask, SecurityProject
from app.services.source_intake import ArchiveSafetyPolicy, ArchiveValidationError, validate_and_extract_zip
from app.services.task_dispatcher import get_scan_task_dispatcher
from app.services.workspaces import AuthorizationError, get_or_create_personal_workspace, require_workspace_role

projects_bp = Blueprint("projects", __name__)
PROJECT_ROLES = {"owner", "security_admin", "analyst", "developer"}
READ_ROLES = PROJECT_ROLES | {"viewer"}


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _policy_from_config() -> ArchiveSafetyPolicy:
    return ArchiveSafetyPolicy(
        max_archive_bytes=int(current_app.config["ARCHIVE_MAX_UPLOAD_BYTES"]),
        max_extracted_bytes=int(current_app.config["ARCHIVE_MAX_EXTRACT_BYTES"]),
        max_file_count=int(current_app.config["ARCHIVE_MAX_FILES"]),
        max_path_depth=int(current_app.config["ARCHIVE_MAX_DEPTH"]),
    )


def _project_or_404(project_id: int) -> SecurityProject:
    project = db.session.get(SecurityProject, project_id)
    if project is None:
        return None
    require_workspace_role(project.workspace_id, _current_user_id(), READ_ROLES)
    return project


def _task_or_404(task_id: int) -> ScanTask:
    task = db.session.get(ScanTask, task_id)
    if task is None:
        return None
    require_workspace_role(task.snapshot.project.workspace_id, _current_user_id(), READ_ROLES)
    return task


def _archive_file() -> FileStorage:
    archive = request.files.get("archive")
    if archive is None or not archive.filename:
        raise ArchiveValidationError("请上传 ZIP 项目压缩包")
    if not archive.filename.lower().endswith(".zip"):
        raise ArchiveValidationError("仅支持 ZIP 项目压缩包")
    return archive


@projects_bp.route("/projects", methods=["POST"])
@jwt_required()
def create_project():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 200:
        return jsonify({"error": "项目名称长度必须在 1 到 200 个字符之间"}), 400

    try:
        user_id = _current_user_id()
        workspace = get_or_create_personal_workspace(user_id)
        require_workspace_role(workspace.id, user_id, {"owner", "security_admin", "analyst", "developer"})
        project = SecurityProject(workspace_id=workspace.id, name=name, created_by=user_id)
        db.session.add(project)
        db.session.commit()
        return jsonify({"project": project.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception:
        db.session.rollback()
        return jsonify({"error": "创建项目失败"}), 409


@projects_bp.route("/projects", methods=["GET"])
@jwt_required()
def list_projects():
    try:
        workspace = get_or_create_personal_workspace(_current_user_id())
        require_workspace_role(workspace.id, _current_user_id(), READ_ROLES)
        projects = SecurityProject.query.filter_by(workspace_id=workspace.id).order_by(SecurityProject.updated_at.desc()).all()
        return jsonify({"items": [project.to_dict() for project in projects]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/projects/<int:project_id>/snapshots:upload", methods=["POST"])
@jwt_required()
def upload_snapshot(project_id: int):
    staging_root: Path | None = None
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        archive = _archive_file()

        workspace_root = Path(current_app.config["SECURITY_WORKSPACE_ROOT"])
        scan_token = uuid4().hex
        staging_root = workspace_root / "staging" / scan_token
        staging_root.mkdir(parents=True, exist_ok=False)
        archive_path = staging_root / "source.zip"
        archive.save(archive_path)

        snapshot_root = workspace_root / "snapshots" / str(project.workspace_id) / str(project.id) / scan_token
        manifest = validate_and_extract_zip(archive_path, snapshot_root, _policy_from_config())
        rmtree(staging_root, ignore_errors=True)
        staging_root = None

        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            source_ref="uploaded_zip",
            content_sha256=manifest.content_sha256,
            storage_path=str(manifest.snapshot_root),
            file_count=manifest.file_count,
            total_bytes=manifest.extracted_bytes,
        )
        db.session.add(snapshot)
        db.session.flush()
        task = ScanTask(snapshot_id=snapshot.id, status="created", progress=0, policy_version="python-baseline-v1")
        db.session.add(task)
        db.session.flush()
        db.session.add(
            AuditEvent(
                workspace_id=project.workspace_id,
                actor_id=user_id,
                action="scan.uploaded",
                target_type="scan_task",
                target_id=task.id,
                metadata_json={
                    "source_type": "zip",
                    "snapshot_id": snapshot.id,
                    "file_count": manifest.file_count,
                    "skipped_files_count": len(manifest.skipped_files),
                },
            )
        )
        db.session.commit()

        get_scan_task_dispatcher().enqueue(task.id)
        task = db.session.get(ScanTask, task.id)
        response = {"snapshot": snapshot.to_dict(), "task": task.to_dict()}
        if current_app.config.get("RQ_ASYNC", False):
            response["task"]["queued"] = True
        return jsonify(response), 202
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ArchiveValidationError as exc:
        if staging_root is not None:
            rmtree(staging_root, ignore_errors=True)
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        if staging_root is not None:
            rmtree(staging_root, ignore_errors=True)
        return jsonify({"error": "创建扫描任务失败"}), 500


@projects_bp.route("/projects/<int:project_id>/tasks", methods=["GET"])
@jwt_required()
def list_project_tasks(project_id: int):
    try:
        project = _project_or_404(project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        tasks = (
            ScanTask.query.join(ProjectSnapshot)
            .filter(ProjectSnapshot.project_id == project.id)
            .order_by(ScanTask.created_at.desc())
            .all()
        )
        return jsonify({"items": [task.to_dict() for task in tasks]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/tasks/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id: int):
    try:
        task = _task_or_404(task_id)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        return jsonify({"task": task.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/tasks/<int:task_id>/findings", methods=["GET"])
@jwt_required()
def get_task_findings(task_id: int):
    try:
        task = _task_or_404(task_id)
        if task is None:
            return jsonify({"error": "扫描任务不存在"}), 404
        findings = task.findings
        return jsonify({"items": [finding.to_dict(include_evidence=True) for finding in findings]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
