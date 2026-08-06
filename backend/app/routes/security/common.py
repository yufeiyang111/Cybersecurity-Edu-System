"""Shared authorization and request-validation helpers for security routes."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import request
from flask_jwt_extended import get_jwt_identity
from werkzeug.datastructures import FileStorage

from app import db
from app.models.security import (
    ProjectSnapshot,
    RemediationSuggestion,
    ScanTask,
    SecurityFinding,
    SecurityKnowledgeDocument,
    SecurityKnowledgeSource,
    SecurityProject,
)
from app.services.source_intake import ArchiveValidationError
from app.services.workspaces import AuthorizationError, get_or_create_personal_workspace, require_workspace_role

PROJECT_ROLES = {"owner", "security_admin", "analyst", "developer"}
READ_ROLES = PROJECT_ROLES | {"viewer"}
KNOWLEDGE_ADMIN_ROLES = {"owner", "security_admin"}
MAX_LIST_LIMIT = 100
DEFAULT_LIST_LIMIT = 20
MAX_KNOWLEDGE_DOCUMENT_CHARS = 100_000
MAX_REVIEW_COMMENT_CHARS = 4_000

def _current_user_id() -> int:
    return int(get_jwt_identity())



def _project_or_404(project_id: int) -> SecurityProject:
    project = db.session.get(SecurityProject, project_id)
    if project is None:
        return None
    require_workspace_role(project.workspace_id, _current_user_id(), READ_ROLES)
    return project


def _task_or_404(task_id: int, allowed_roles: set[str] = READ_ROLES) -> ScanTask:
    task = db.session.get(ScanTask, task_id)
    if task is None:
        return None
    require_workspace_role(task.snapshot.project.workspace_id, _current_user_id(), allowed_roles)
    return task


def _archive_file() -> FileStorage:
    archive = request.files.get("archive")
    if archive is None or not archive.filename:
        raise ArchiveValidationError("请上传 ZIP 项目压缩包")
    if not archive.filename.lower().endswith(".zip"):
        raise ArchiveValidationError("仅支持 ZIP 项目压缩包")
    return archive



def _finding_or_404(finding_id: int, allowed_roles: set[str] = READ_ROLES) -> SecurityFinding | None:
    finding = db.session.get(SecurityFinding, finding_id)
    if finding is None:
        return None
    require_workspace_role(finding.task.snapshot.project.workspace_id, _current_user_id(), allowed_roles)
    return finding


def _suggestion_or_404(
    suggestion_id: int,
    allowed_roles: set[str] = READ_ROLES,
) -> RemediationSuggestion | None:
    suggestion = db.session.get(RemediationSuggestion, suggestion_id)
    if suggestion is None:
        return None
    require_workspace_role(
        suggestion.finding.task.snapshot.project.workspace_id,
        _current_user_id(),
        allowed_roles,
    )
    return suggestion


def _knowledge_source_or_404(
    source_id: int,
    allowed_roles: set[str] = KNOWLEDGE_ADMIN_ROLES,
) -> SecurityKnowledgeSource | None:
    source = db.session.get(SecurityKnowledgeSource, source_id)
    if source is None:
        return None
    require_workspace_role(source.workspace_id, _current_user_id(), allowed_roles)
    return source


def _knowledge_document_or_404(
    source_id: int,
    document_id: int,
    allowed_roles: set[str] = KNOWLEDGE_ADMIN_ROLES,
) -> SecurityKnowledgeDocument | None:
    document = db.session.get(SecurityKnowledgeDocument, document_id)
    if document is None or document.source_id != source_id:
        return None
    require_workspace_role(document.source.workspace_id, _current_user_id(), allowed_roles)
    return document


def _json_object() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("请求体必须是 JSON 对象")
    return data


def _required_text(data: dict, field: str, maximum: int) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是字符串")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field} 长度必须在 1 至 {maximum} 个字符之间")
    return normalized


def _optional_text(data: dict, field: str, maximum: int) -> str | None:
    if field not in data or data[field] is None:
        return None
    value = data[field]
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是字符串")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{field} 长度不能超过 {maximum} 个字符")
    return normalized or None


def _optional_bool(data: dict, field: str, default: bool) -> bool:
    if field not in data:
        return default
    value = data[field]
    if not isinstance(value, bool):
        raise ValueError(f"{field} 必须是布尔值")
    return value


def _optional_datetime(data: dict, field: str) -> datetime | None:
    value = _optional_text(data, field, 64)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} 必须是 ISO 8601 时间") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _source_uri(data: dict) -> str | None:
    value = _optional_text(data, "source_uri", 2048)
    if value is None:
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("source_uri 必须是带有 HTTP(S) 协议的合法 URL")
    return value


def _document_tags(data: dict) -> list[str]:
    raw_tags = data.get("tags", [])
    if not isinstance(raw_tags, list) or len(raw_tags) > 30:
        raise ValueError("tags 最多包含 30 个标签")
    tags: list[str] = []
    for item in raw_tags:
        if not isinstance(item, str):
            raise ValueError("tags 必须是字符串数组")
        tag = item.strip()
        if not tag or len(tag) > 100:
            raise ValueError("单个 tag 长度必须在 1 至 100 个字符之间")
        if tag not in tags:
            tags.append(tag)
    return tags


def _list_params() -> tuple[int, int]:
    limit = request.args.get("limit", DEFAULT_LIST_LIMIT, type=int)
    offset = request.args.get("offset", 0, type=int)
    if limit is None or offset is None or not 1 <= limit <= MAX_LIST_LIMIT or offset < 0:
        raise ValueError(f"limit 必须在 1 至 {MAX_LIST_LIMIT} 之间，offset 不能小于 0")
    return limit, offset


def _pagination_payload(*, total: int, limit: int, offset: int) -> dict:
    return {"total": total, "limit": limit, "offset": offset}


def _effective_range_is_valid(effective_from: datetime | None, effective_until: datetime | None) -> bool:
    return effective_until is None or effective_from is None or effective_until >= effective_from
