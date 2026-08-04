"""安全工作台聚合查询服务。

按项目聚合最近一次扫描结果，为工作台总览提供确定性的只读数据。
仅返回 normalized 的非敏感字段，绝不触碰快照源码内容。
"""
from __future__ import annotations

from sqlalchemy import func

from app import db
from app.models.security import ProjectSnapshot, ScanTask, SecurityFinding, SecurityProject

RUNNING_STATUSES = {"created", "validating", "snapshotting", "scanning"}
SEVERITY_KEYS = ("critical", "high", "medium", "low", "info")

FALLBACK_LANGUAGE = "unknown"


def build_workspace_dashboard(workspace_id: int) -> dict:
    """构造安全工作台聚合数据：项目汇总、漏洞总量与最近扫描记录。

    项目漏洞分布取「该项目最近一次扫描任务」的 findings，避免多次扫描重复累计；
    因此项目卡片分布之和等于总览卡的漏洞总量。
    """
    projects = (
        SecurityProject.query.filter_by(workspace_id=workspace_id)
        .order_by(SecurityProject.updated_at.desc(), SecurityProject.id.desc())
        .all()
    )
    project_ids = [project.id for project in projects]

    tasks_by_project = dict(_latest_task_ids_by_project(project_ids))
    task_ids = list(tasks_by_project.values())
    task_by_id = {task.id: task for task in ScanTask.query.filter(ScanTask.id.in_(task_ids))}

    finding_totals = _severity_totals(task_ids)
    scan_totals = _scan_totals_by_project(project_ids)
    snapshot_rows = _latest_snapshot_by_project(project_ids)

    project_items = []
    totals = dict.fromkeys(SEVERITY_KEYS, 0)
    for project in projects:
        task_id = tasks_by_project.get(project.id)
        task = task_by_id.get(task_id) if task_id is not None else None
        counts = finding_totals.get(task_id, {}) if task_id is not None else {}
        for key in SEVERITY_KEYS:
            totals[key] += counts.get(key, 0)

        last_scan_at = None
        if task is not None:
            last_scan_at = (
                task.finished_at or task.canceled_at or task.started_at or task.created_at
            )
        snapshot_id, file_count = snapshot_rows.get(project.id, (None, 0))
        project_items.append(
            {
                **project.to_dict(),
                "language": _primary_language(task),
                "scan_status": task.status if task is not None else None,
                "is_running": bool(task is not None and task.status in RUNNING_STATUSES),
                "scan_count": scan_totals.get(project.id, 0),
                "latest_task_id": task_id,
                "latest_snapshot_id": snapshot_id,
                "files": file_count,
                "last_scan_at": last_scan_at.isoformat() if last_scan_at else None,
                "vulns": {"total": sum(counts.values()), **counts},
            }
        )

    return {
        "projects": project_items,
        "total_projects": len(projects),
        "total_scans": sum(scan_totals.values()),
        "totals": totals,
        "recent_scans": _recent_scans(workspace_id, limit=6),
    }


def _latest_task_ids_by_project(project_ids: list[int]) -> list[tuple[int, int]]:
    if not project_ids:
        return []
    rows = (
        db.session.query(
            ProjectSnapshot.project_id, func.max(ScanTask.id).label("task_id")
        )
        .join(ScanTask, ScanTask.snapshot_id == ProjectSnapshot.id)
        .filter(ProjectSnapshot.project_id.in_(project_ids))
        .group_by(ProjectSnapshot.project_id)
        .all()
    )
    return [(project_id, task_id) for project_id, task_id in rows if task_id is not None]


def _severity_totals(task_ids: list[int]) -> dict[int, dict[str, int]]:
    if not task_ids:
        return {}
    rows = (
        db.session.query(
            SecurityFinding.task_id,
            SecurityFinding.severity,
            func.count(SecurityFinding.id),
        )
        .filter(SecurityFinding.task_id.in_(task_ids))
        .group_by(SecurityFinding.task_id, SecurityFinding.severity)
        .all()
    )
    totals: dict[int, dict[str, int]] = {}
    for task_id, severity, count in rows:
        totals.setdefault(task_id, {})[severity] = count
    return totals


def _scan_totals_by_project(project_ids: list[int]) -> dict[int, int]:
    if not project_ids:
        return {}
    rows = (
        db.session.query(ProjectSnapshot.project_id, func.count(ScanTask.id))
        .join(ScanTask, ScanTask.snapshot_id == ProjectSnapshot.id)
        .filter(ProjectSnapshot.project_id.in_(project_ids))
        .group_by(ProjectSnapshot.project_id)
        .all()
    )
    return {project_id: count for project_id, count in rows}


def _latest_snapshot_by_project(project_ids: list[int]) -> dict[int, tuple[int | None, int]]:
    if not project_ids:
        return {}
    rows = (
        db.session.query(ProjectSnapshot.id, ProjectSnapshot.project_id, ProjectSnapshot.file_count)
        .filter(ProjectSnapshot.project_id.in_(project_ids))
        .order_by(ProjectSnapshot.created_at.desc(), ProjectSnapshot.id.desc())
        .all()
    )
    results: dict[int, tuple[int | None, int]] = {}
    for snapshot_id, project_id, file_count in rows:
        results.setdefault(project_id, (snapshot_id, file_count or 0))
    return results


def _primary_language(task: ScanTask | None) -> str:
    if task is None or not isinstance(task.summary_json, dict):
        return FALLBACK_LANGUAGE
    languages = task.summary_json.get("languages") or []
    if not languages:
        return FALLBACK_LANGUAGE
    return str(languages[0]).strip().lower() or FALLBACK_LANGUAGE


def _recent_scans(workspace_id: int, limit: int) -> list[dict]:
    if limit < 0:
        limit = 0
    tasks = (
        ScanTask.query.join(ProjectSnapshot, ProjectSnapshot.id == ScanTask.snapshot_id)
        .join(SecurityProject, SecurityProject.id == ProjectSnapshot.project_id)
        .filter(SecurityProject.workspace_id == workspace_id)
        .order_by(ScanTask.created_at.desc(), ScanTask.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for task in tasks:
        snapshot = task.snapshot
        project = snapshot.project
        summary = task.summary_json if isinstance(task.summary_json, dict) else {}
        items.append(
            {
                "task_id": task.id,
                "project_id": project.id,
                "project_name": project.name,
                "language": _primary_language(task),
                "status": task.status.value if hasattr(task.status, "value") else task.status,
                "findings_count": summary.get("findings_count", 0),
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            }
        )
    return items


__all__ = ["build_workspace_dashboard"]