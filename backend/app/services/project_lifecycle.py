# -*- coding: utf-8 -*-
"""项目、快照和扫描任务的删除编排服务。

负责删除前的引用检查（Agent 运行记录、Agent 会话）、快照磁盘目录清理、
审计记录与级联删除。路由层只做授权和异常映射，不包含业务编排。
"""
from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from typing import Any, Iterable

from sqlalchemy import update

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentArtifact,
    AgentCheckpoint,
    AgentMessage,
    AgentPlan,
    AgentPlanEdge,
    AgentPlanNode,
    AgentRun,
    AgentStepExecution,
    AgentToolCall,
)
from app.models.conversation import AgentConversation, AgentConversationMessage, AgentTurn
from app.models.security import AuditEvent, ProjectSnapshot, ScanTask, SecurityProject


class ProjectLifecycleError(RuntimeError):
    """删除项目、快照或任务时发生的业务约束失败。"""


def _audit(workspace_id: int, actor_id: int, action: str, target_type: str, target_id: int, metadata: dict[str, Any] | None = None) -> None:
    db.session.add(
        AuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata,
        )
    )


def _snapshot_disk_path(snapshot: ProjectSnapshot, workspace_root: str) -> Path | None:
    """将存储路径规范化并限制在安全工作目录内，防止删除越界目录。"""
    if not snapshot.storage_path:
        return None
    try:
        resolved = Path(snapshot.storage_path).resolve()
    except OSError:
        return None
    allowed_root = Path(workspace_root).resolve() / "snapshots"
    if allowed_root not in resolved.parents:
        return None
    return resolved


def _delete_snapshot_files(snapshot: ProjectSnapshot, workspace_root: str) -> None:
    """删除快照在磁盘上的只读目录；路径不在安全目录内时跳过。"""
    disk_path = _snapshot_disk_path(snapshot, workspace_root)
    if disk_path is not None and disk_path.exists():
        rmtree(disk_path, ignore_errors=True)


def delete_scan_task(task: ScanTask, actor_id: int) -> None:
    """删除任务前校验终态；级联删除发现项、证据、修复建议和覆盖率单据。"""
    status = task.status.value if hasattr(task.status, "value") else task.status
    if status not in {"completed", "completed_with_warnings", "failed", "canceled"}:
        raise ProjectLifecycleError("只有已结束的扫描任务可以删除")
    workspace_id = task.snapshot.project.workspace_id
    _audit(workspace_id, actor_id, "scan_task.deleted", "scan_task", task.id, {"status": status})
    db.session.delete(task)
    db.session.commit()


def delete_snapshot(snapshot: ProjectSnapshot, actor_id: int, workspace_root: str) -> None:
    """删除快照：清理磁盘后级联删除，Agent运行记录随项目删除而自动清理。"""
    db.session.execute(
        update(AgentConversation)
        .where(AgentConversation.current_snapshot_id == snapshot.id)
        .values(current_snapshot_id=None)
    )
    workspace_id = snapshot.project.workspace_id
    _delete_snapshot_files(snapshot, workspace_root)
    _audit(
        workspace_id,
        actor_id,
        "snapshot.deleted",
        "project_snapshot",
        snapshot.id,
        {"project_id": snapshot.project_id, "source_type": snapshot.source_type},
    )
    db.session.delete(snapshot)
    db.session.commit()


def delete_project(project: SecurityProject, actor_id: int, workspace_root: str) -> None:
    """删除项目：清理快照磁盘后级联删除所有关联记录（Agent会话、Agent运行、快照等）。"""
    snapshot_count = _snapshot_count(project.id)
    conversation_count = AgentConversation.query.filter_by(project_id=project.id).count()
    run_count = AgentRun.query.filter_by(project_id=project.id).count()

    _delete_agent_records(project.id)

    for snapshot in ProjectSnapshot.query.filter_by(project_id=project.id).all():
        _delete_snapshot_files(snapshot, workspace_root)

    _audit(
        project.workspace_id,
        actor_id,
        "project.deleted",
        "security_project",
        project.id,
        {
            "snapshot_count": snapshot_count,
            "conversation_count": conversation_count,
            "run_count": run_count,
        },
    )
    db.session.delete(project)
    db.session.commit()


def _delete_agent_records(project_id: int) -> None:
    """按外键依赖顺序清理项目下的 Agent 会话与运行记录。

    agent_conversation_messages 与 agent_turns 互相引用（turn_id / input_message_id），
    agent_runs 下有 7 张引用表，且历史迁移未声明 ON DELETE CASCADE，
    因此必须显式按依赖顺序删除，避免外键约束失败。
    """
    conversation_ids = [
        row[0]
        for row in db.session.query(AgentConversation.id)
        .filter_by(project_id=project_id)
        .all()
    ]
    run_ids = [
        row[0]
        for row in db.session.query(AgentRun.id).filter_by(project_id=project_id).all()
    ]
    if conversation_ids:
        db.session.execute(
            update(AgentTurn)
            .where(AgentTurn.conversation_id.in_(conversation_ids))
            .values(input_message_id=None, parent_turn_id=None)
        )
        db.session.execute(
            AgentConversationMessage.__table__.delete().where(
                AgentConversationMessage.conversation_id.in_(conversation_ids)
            )
        )
        db.session.execute(
            AgentTurn.__table__.delete().where(
                AgentTurn.conversation_id.in_(conversation_ids)
            )
        )
        db.session.execute(
            AgentConversation.__table__.delete().where(
                AgentConversation.id.in_(conversation_ids)
            )
        )
    if run_ids:
        db.session.execute(
            AgentToolCall.__table__.delete().where(AgentToolCall.run_id.in_(run_ids))
        )
        db.session.execute(
            AgentArtifact.__table__.delete().where(AgentArtifact.run_id.in_(run_ids))
        )
        db.session.execute(
            AgentStepExecution.__table__.delete().where(
                AgentStepExecution.run_id.in_(run_ids)
            )
        )
        plan_ids = [
            row[0]
            for row in db.session.query(AgentPlan.id).filter(AgentPlan.run_id.in_(run_ids)).all()
        ]
        if plan_ids:
            db.session.execute(
                AgentPlanEdge.__table__.delete().where(AgentPlanEdge.plan_id.in_(plan_ids))
            )
            db.session.execute(
                AgentPlanNode.__table__.delete().where(AgentPlanNode.plan_id.in_(plan_ids))
            )
            db.session.execute(
                AgentPlan.__table__.delete().where(AgentPlan.id.in_(plan_ids))
            )
        db.session.execute(
            AgentMessage.__table__.delete().where(AgentMessage.run_id.in_(run_ids))
        )
        db.session.execute(
            AgentCheckpoint.__table__.delete().where(AgentCheckpoint.run_id.in_(run_ids))
        )
        db.session.execute(
            AgentEvent.__table__.delete().where(AgentEvent.run_id.in_(run_ids))
        )
        db.session.execute(
            AgentRun.__table__.delete().where(AgentRun.id.in_(run_ids))
        )


def _snapshot_count(project_id: int) -> int:
    return ProjectSnapshot.query.filter_by(project_id=project_id).count()


__all__ = ["ProjectLifecycleError", "delete_project", "delete_scan_task", "delete_snapshot"]
