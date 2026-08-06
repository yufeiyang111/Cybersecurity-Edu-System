"""Safe ZIP and public GitHub snapshot intake endpoints."""
from __future__ import annotations

from flask import current_app, jsonify, request
from app.services.rate_limit import rate_limit
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app import db
from app.models.security import ProjectSnapshot, ScanTask, SecurityProject
from app.services.github_source import GitHubSourceError
from app.services.project_lifecycle import ProjectLifecycleError, delete_snapshot
from app.services.snapshot_service import (
    SnapshotCreationError,
    create_github_snapshot,
    create_rescan_task,
    create_uploaded_snapshot,
)
from app.services.source_intake import ArchiveValidationError

from . import projects_bp
from .common import (
    AuthorizationError,
    PROJECT_ROLES,
    READ_ROLES,
    _archive_file,
    _current_user_id,
    _list_params,
    _pagination_payload,
    require_workspace_role,
)


@projects_bp.route("/projects/<int:project_id>/snapshots:upload", methods=["POST"])
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def upload_snapshot(project_id: int):
    """接收已授权用户的 ZIP 请求，并交由快照应用服务处理。"""
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        result = create_uploaded_snapshot(project, user_id, _archive_file(), current_app.config)
        return jsonify(result.to_response()), 202
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ArchiveValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except SnapshotCreationError as exc:
        current_app.logger.exception(
            "Security snapshot upload failed (project_id=%s, stage=%s)",
            project_id,
            exc.stage,
        )
        return jsonify({"error": "创建扫描任务失败"}), 500


@projects_bp.route("/projects/<int:project_id>/snapshots:github", methods=["POST"])
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def import_github_snapshot(project_id: int):
    """导入公共 GitHub 固定 commit 快照，不 clone、不执行仓库代码。"""
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        data = request.get_json(silent=True) or {}
        repository_url = str(data.get("repository_url", "")).strip()
        if not repository_url:
            return jsonify({"error": "请提供 GitHub 仓库地址"}), 400
        result = create_github_snapshot(project, user_id, repository_url, current_app.config)
        return jsonify(result.to_response()), 202
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except (GitHubSourceError, ArchiveValidationError) as exc:
        return jsonify({"error": str(exc)}), 400
    except SnapshotCreationError as exc:
        current_app.logger.exception(
            "Security GitHub snapshot import failed (project_id=%s, stage=%s)",
            project_id,
            exc.stage,
        )
        return jsonify({"error": "创建 GitHub 扫描任务失败"}), 502


@projects_bp.route("/projects/<int:project_id>/rescan", methods=["POST"])
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def rescan_project(project_id: int):
    """对项目最近一次快照发起全新扫描，不重新上传代码。"""
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)
        result = create_rescan_task(project, user_id, current_app.config)
        return jsonify(result.to_response()), 202
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except (GitHubSourceError, ArchiveValidationError) as exc:
        return jsonify({"error": str(exc)}), 400
    except SnapshotCreationError as exc:
        current_app.logger.exception(
            "Security rescan failed (project_id=%s, stage=%s)",
            project_id,
            exc.stage,
        )
        return jsonify({"error": "重新扫描失败"}), 502


@projects_bp.route("/projects/<int:project_id>/snapshots", methods=["GET"])
@jwt_required()
def list_snapshots(project_id: int):
    """分页列出项目的快照及其任务统计。"""
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        require_workspace_role(project.workspace_id, _current_user_id(), READ_ROLES)
        query = ProjectSnapshot.query.filter_by(project_id=project.id)
        total = query.count()
        limit, offset = _list_params()
        snapshots = (
            query.order_by(ProjectSnapshot.created_at.desc(), ProjectSnapshot.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        snapshot_ids = [snapshot.id for snapshot in snapshots]
        task_counts = {}
        if snapshot_ids:
            rows = (
                db.session.query(ScanTask.snapshot_id, func.count(ScanTask.id))
                .filter(ScanTask.snapshot_id.in_(snapshot_ids))
                .group_by(ScanTask.snapshot_id)
                .all()
            )
            task_counts = {snapshot_id: count for snapshot_id, count in rows}
        items = []
        for snapshot in snapshots:
            item = snapshot.to_dict()
            item["task_count"] = task_counts.get(snapshot.id, 0)
            items.append(item)
        return jsonify(
            {
                "items": items,
                "pagination": _pagination_payload(total=total, limit=limit, offset=offset),
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/projects/<int:project_id>/snapshots/<int:snapshot_id>", methods=["DELETE"])
@jwt_required()
def delete_snapshot_endpoint(project_id: int, snapshot_id: int):
    """删除快照：拒绝被 Agent 运行引用，级联删除任务、发现项与磁盘目录。"""
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        require_workspace_role(project.workspace_id, _current_user_id(), PROJECT_ROLES)
        snapshot = db.session.get(ProjectSnapshot, snapshot_id)
        if snapshot is None or snapshot.project_id != project.id:
            return jsonify({"error": "快照不存在"}), 404
        workspace_root = str(current_app.config["SECURITY_WORKSPACE_ROOT"])
        delete_snapshot(snapshot, _current_user_id(), workspace_root)
        return jsonify({"deleted": True})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ProjectLifecycleError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("删除快照失败 (project_id=%s, snapshot_id=%s)", project_id, snapshot_id)
        return jsonify({"error": "删除快照失败"}), 500
