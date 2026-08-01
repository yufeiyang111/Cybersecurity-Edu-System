"""Safe ZIP and public GitHub snapshot intake endpoints."""
from __future__ import annotations

from flask import current_app, jsonify, request
from app.services.rate_limit import rate_limit
from flask_jwt_extended import jwt_required

from app import db
from app.models.security import SecurityProject
from app.services.github_source import GitHubSourceError
from app.services.snapshot_service import (
    SnapshotCreationError,
    create_github_snapshot,
    create_uploaded_snapshot,
)
from app.services.source_intake import ArchiveValidationError

from . import projects_bp
from .common import (
    AuthorizationError,
    PROJECT_ROLES,
    _archive_file,
    _current_user_id,
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
