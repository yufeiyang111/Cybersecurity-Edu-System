"""安全项目快照创建应用服务。

该模块负责安全 ZIP 和公共 GitHub 快照的落盘、模型持久化、审计和扫描任务派发。
HTTP 路由只负责授权、请求解析和异常到状态码的映射。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from shutil import rmtree
from typing import Any, Mapping
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from app import db
from app.models.security import AuditEvent, ProjectSnapshot, ScanTask, SecurityProject
from app.services.github_source import GitHubSourceError, download_public_github_archive
from app.services.source_intake import (
    ArchiveSafetyPolicy,
    ArchiveValidationError,
    SnapshotManifest,
    validate_and_extract_zip,
)
from app.services.scan_task_lifecycle import (
    mark_dispatch_failed,
    new_dispatch_key,
    is_terminal_status,
)
from app.services.task_dispatcher import ScanTaskDispatcher, get_scan_task_dispatcher


GITHUB_ARCHIVE_WRAPPER_DEPTH = 1


class SnapshotCreationError(RuntimeError):
    """快照创建的内部失败，保留安全阶段名称供服务端日志使用。"""

    def __init__(self, message: str, *, stage: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class SnapshotTaskResult:
    """已经提交并派发的快照与扫描任务。"""

    snapshot: ProjectSnapshot
    task: ScanTask
    queued: bool

    def to_response(self) -> dict[str, dict[str, Any]]:
        """序列化为与既有 HTTP API 兼容的响应结构。"""
        task = db.session.get(ScanTask, self.task.id) or self.task
        task_payload = task.to_dict()
        if self.queued:
            task_payload["queued"] = True
        return {"snapshot": self.snapshot.to_dict(), "task": task_payload}


def archive_policy_from_settings(settings: Mapping[str, Any]) -> ArchiveSafetyPolicy:
    """从应用配置构造普通用户上传 ZIP 的严格安全策略。"""
    return ArchiveSafetyPolicy(
        max_archive_bytes=int(settings["ARCHIVE_MAX_UPLOAD_BYTES"]),
        max_extracted_bytes=int(settings["ARCHIVE_MAX_EXTRACT_BYTES"]),
        max_file_count=int(settings["ARCHIVE_MAX_FILES"]),
        max_path_depth=int(settings["ARCHIVE_MAX_DEPTH"]),
    )


def github_archive_policy(settings: Mapping[str, Any]) -> ArchiveSafetyPolicy:
    """仅为 GitHub zipball 的顶层仓库目录额外放宽一层深度。"""
    policy = archive_policy_from_settings(settings)
    return replace(policy, max_path_depth=policy.max_path_depth + GITHUB_ARCHIVE_WRAPPER_DEPTH)


def create_uploaded_snapshot(
    project: SecurityProject,
    actor_id: int,
    archive: FileStorage,
    settings: Mapping[str, Any],
    *,
    dispatcher: ScanTaskDispatcher | None = None,
) -> SnapshotTaskResult:
    """创建用户 ZIP 快照并派发扫描，不执行压缩包中的任何代码。"""
    staging_root: Path | None = None
    stage = "create_staging_directory"
    try:
        workspace_root = Path(str(settings["SECURITY_WORKSPACE_ROOT"]))
        scan_token = uuid4().hex
        staging_root = workspace_root / "staging" / scan_token
        staging_root.mkdir(parents=True, exist_ok=False)
        archive_path = staging_root / "source.zip"

        stage = "save_archive"
        archive.save(archive_path)
        stage = "extract_archive"
        snapshot_root = workspace_root / "snapshots" / str(project.workspace_id) / str(project.id) / scan_token
        manifest = validate_and_extract_zip(archive_path, snapshot_root, archive_policy_from_settings(settings))
        rmtree(staging_root, ignore_errors=True)
        staging_root = None

        stage = "persist_snapshot"
        result = _persist_and_dispatch(
            project=project,
            actor_id=actor_id,
            manifest=manifest,
            source_type="zip",
            source_ref="uploaded_zip",
            commit_sha=None,
            action="scan.uploaded",
            policy_version="python-baseline-v1",
            settings=settings,
            dispatcher=dispatcher,
        )
        return result
    except Exception as exc:
        if staging_root is not None:
            rmtree(staging_root, ignore_errors=True)
        if isinstance(exc, (ArchiveValidationError, SnapshotCreationError)):
            raise
        db.session.rollback()
        raise SnapshotCreationError("创建扫描任务失败", stage=stage) from exc


def create_github_snapshot(
    project: SecurityProject,
    actor_id: int,
    repository_url: str,
    settings: Mapping[str, Any],
    *,
    dispatcher: ScanTaskDispatcher | None = None,
) -> SnapshotTaskResult:
    """下载固定 commit 的公共 GitHub zipball，验证后创建只读扫描快照。"""
    staging_root: Path | None = None
    stage = "create_staging_directory"
    try:
        workspace_root = Path(str(settings["SECURITY_WORKSPACE_ROOT"]))
        scan_token = uuid4().hex
        staging_root = workspace_root / "staging" / scan_token
        staging_root.mkdir(parents=True, exist_ok=False)
        archive_path = staging_root / "github-source.zip"

        stage = "download_public_github_archive"
        github_archive = download_public_github_archive(
            repository_url,
            archive_path,
            int(settings["ARCHIVE_MAX_UPLOAD_BYTES"]),
            int(settings["GITHUB_API_TIMEOUT_SECONDS"]),
            int(settings["GITHUB_MAX_REDIRECTS"]),
        )
        stage = "extract_archive"
        snapshot_root = workspace_root / "snapshots" / str(project.workspace_id) / str(project.id) / scan_token
        manifest = validate_and_extract_zip(archive_path, snapshot_root, github_archive_policy(settings))
        rmtree(staging_root, ignore_errors=True)
        staging_root = None

        stage = "persist_snapshot"
        return _persist_and_dispatch(
            project=project,
            actor_id=actor_id,
            manifest=manifest,
            source_type="github",
            source_ref=github_archive.repository.normalized_url,
            commit_sha=github_archive.commit_sha,
            action="scan.github_imported",
            policy_version="baseline-rules-v2",
            settings=settings,
            dispatcher=dispatcher,
        )
    except Exception as exc:
        if staging_root is not None:
            rmtree(staging_root, ignore_errors=True)
        if isinstance(exc, (ArchiveValidationError, GitHubSourceError, SnapshotCreationError)):
            raise
        db.session.rollback()
        raise SnapshotCreationError("创建 GitHub 扫描任务失败", stage=stage) from exc


def _persist_and_dispatch(
    *,
    project: SecurityProject,
    actor_id: int,
    manifest: SnapshotManifest,
    source_type: str,
    source_ref: str,
    commit_sha: str | None,
    action: str,
    policy_version: str,
    settings: Mapping[str, Any],
    dispatcher: ScanTaskDispatcher | None,
) -> SnapshotTaskResult:
    """以内容哈希去重快照，事务提交后再使用幂等键派发任务。"""
    existing_snapshot = ProjectSnapshot.query.filter_by(
        project_id=project.id,
        content_sha256=manifest.content_sha256,
    ).one_or_none()
    if existing_snapshot is not None:
        # 新解压目录只用于计算清单；复用已有快照时必须清理临时目录。
        rmtree(manifest.snapshot_root, ignore_errors=True)
        snapshot = existing_snapshot
        latest_task = (
            ScanTask.query.filter_by(snapshot_id=snapshot.id)
            .order_by(ScanTask.created_at.desc(), ScanTask.id.desc())
            .first()
        )
        if latest_task is not None and not is_terminal_status(latest_task.status):
            return SnapshotTaskResult(
                snapshot=snapshot,
                task=latest_task,
                queued=False,
            )
    else:
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type=source_type,
            source_ref=source_ref,
            commit_sha=commit_sha,
            content_sha256=manifest.content_sha256,
            storage_path=str(manifest.snapshot_root),
            file_count=manifest.file_count,
            total_bytes=manifest.extracted_bytes,
        )
        db.session.add(snapshot)
        db.session.flush()

    task = ScanTask(
        snapshot_id=snapshot.id,
        status="created",
        progress=0,
        policy_version=policy_version,
        dispatch_key=new_dispatch_key(),
        retry_count=0,
    )
    db.session.add(task)
    db.session.flush()
    audit_metadata: dict[str, Any] = {
        "source_type": source_type,
        "snapshot_id": snapshot.id,
        "file_count": manifest.file_count,
        "skipped_files_count": len(manifest.skipped_files),
        "deduplicated_snapshot": existing_snapshot is not None,
    }
    if commit_sha:
        audit_metadata["commit_sha"] = commit_sha
    db.session.add(
        AuditEvent(
            workspace_id=project.workspace_id,
            actor_id=actor_id,
            action="scan.snapshot_reused" if existing_snapshot is not None else action,
            target_type="scan_task",
            target_id=task.id,
            metadata_json=audit_metadata,
        )
    )
    db.session.commit()

    task_dispatcher = dispatcher or get_scan_task_dispatcher()
    try:
        task_dispatcher.enqueue(task.id, task.dispatch_key)
    except Exception as exc:
        db.session.rollback()
        mark_dispatch_failed(task.id)
        raise SnapshotCreationError("创建扫描任务失败", stage="dispatch") from exc

    return SnapshotTaskResult(
        snapshot=snapshot,
        task=task,
        queued=bool(settings.get("RQ_ASYNC", False)),
    )