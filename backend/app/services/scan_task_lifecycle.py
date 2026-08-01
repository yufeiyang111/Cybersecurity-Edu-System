"""扫描任务状态机、幂等派发和审计记录。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import update

from app import db
from app.models.security import AuditEvent, ScanTask, ScanTaskStatus


TERMINAL_STATUSES = {
    ScanTaskStatus.COMPLETED.value,
    ScanTaskStatus.COMPLETED_WITH_WARNINGS.value,
    ScanTaskStatus.FAILED.value,
    ScanTaskStatus.CANCELED.value,
}
RETRYABLE_STATUSES = {ScanTaskStatus.FAILED.value, ScanTaskStatus.CANCELED.value}
ALLOWED_TRANSITIONS = {
    ScanTaskStatus.CREATED.value: {
        ScanTaskStatus.VALIDATING.value,
        ScanTaskStatus.FAILED.value,
        ScanTaskStatus.CANCELED.value,
    },
    ScanTaskStatus.VALIDATING.value: {
        ScanTaskStatus.SNAPSHOTTING.value,
        ScanTaskStatus.FAILED.value,
        ScanTaskStatus.CANCELED.value,
    },
    ScanTaskStatus.SNAPSHOTTING.value: {
        ScanTaskStatus.SCANNING.value,
        ScanTaskStatus.FAILED.value,
        ScanTaskStatus.CANCELED.value,
    },
    ScanTaskStatus.SCANNING.value: {
        ScanTaskStatus.COMPLETED.value,
        ScanTaskStatus.COMPLETED_WITH_WARNINGS.value,
        ScanTaskStatus.FAILED.value,
        ScanTaskStatus.CANCELED.value,
    },
    ScanTaskStatus.COMPLETED.value: set(),
    ScanTaskStatus.COMPLETED_WITH_WARNINGS.value: set(),
    ScanTaskStatus.FAILED.value: set(),
    ScanTaskStatus.CANCELED.value: set(),
}


class ScanTaskStateError(ValueError):
    """扫描任务发生非法状态流转时抛出。"""


def status_value(value: object) -> str:
    """兼容 SQLAlchemy 枚举和字符串状态值。"""
    return getattr(value, "value", value)


def is_terminal_status(status: object) -> bool:
    """判断扫描任务是否已经到达终态。"""
    return status_value(status) in TERMINAL_STATUSES


def new_dispatch_key() -> str:
    """生成不包含业务数据的队列幂等键。"""
    return uuid4().hex


def claim_scan_task(task_id: int, worker_id: str | None = None) -> ScanTask | None:
    """使用条件更新抢占 created 任务，避免重复 worker 并发执行同一任务。"""
    task = db.session.get(ScanTask, task_id)
    if task is None or is_terminal_status(task.status):
        return None
    if status_value(task.status) != ScanTaskStatus.CREATED.value:
        return None

    assigned_worker = worker_id or f"worker-{uuid4().hex}"
    result = db.session.execute(
        update(ScanTask)
        .where(
            ScanTask.id == task_id,
            ScanTask.status == ScanTaskStatus.CREATED.value,
            ScanTask.worker_id.is_(None),
        )
        .values(worker_id=assigned_worker)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return None
    db.session.commit()
    return db.session.get(ScanTask, task_id)


def transition_task(task: ScanTask, status: str, progress: int) -> None:
    """执行一次经过约束校验的扫描状态流转。"""
    if not isinstance(progress, int) or not 0 <= progress <= 100:
        raise ScanTaskStateError("扫描任务进度必须在 0 到 100 之间")
    current = status_value(task.status)
    if status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ScanTaskStateError(f"非法扫描任务状态流转: {current} -> {status}")

    task.status = status
    task.progress = progress
    if status == ScanTaskStatus.SCANNING.value and task.started_at is None:
        task.started_at = datetime.utcnow()
    if status in TERMINAL_STATUSES:
        task.finished_at = datetime.utcnow()
    db.session.flush()


def cancel_scan_task(task: ScanTask, actor_id: int | None = None) -> None:
    """取消未结束任务，同时保留已持久化的扫描证据。"""
    if is_terminal_status(task.status):
        raise ScanTaskStateError("已结束的扫描任务不能取消")

    previous_status = status_value(task.status)
    transition_task(task, ScanTaskStatus.CANCELED.value, task.progress)
    task.canceled_at = datetime.utcnow()
    task.error_code = None
    record_task_audit(
        task,
        "scan.canceled",
        {"previous_status": previous_status},
        actor_id=actor_id,
    )
    db.session.commit()


def prepare_scan_task_retry(
    task: ScanTask,
    actor_id: int | None = None,
    *,
    max_retries: int = 3,
) -> ScanTask:
    """将失败或取消任务重置为可再次派发的 created 状态。"""
    current = status_value(task.status)
    if current not in RETRYABLE_STATUSES:
        raise ScanTaskStateError("只有失败或已取消的扫描任务可以重试")
    if not isinstance(max_retries, int) or max_retries <= 0:
        raise ScanTaskStateError("扫描任务最大重试次数配置无效")
    if int(task.retry_count or 0) >= max_retries:
        raise ScanTaskStateError("扫描任务已达到最大重试次数")

    task.status = ScanTaskStatus.CREATED.value
    task.progress = 0
    task.worker_id = None
    task.dispatch_key = new_dispatch_key()
    task.retry_count = int(task.retry_count or 0) + 1
    task.error_code = None
    task.error_message = None
    task.started_at = None
    task.finished_at = None
    task.canceled_at = None
    record_task_audit(
        task,
        "scan.retry_requested",
        {"previous_status": current, "retry_count": task.retry_count},
        actor_id=actor_id,
    )
    db.session.commit()
    return task


def mark_dispatch_failed(task_id: int, *, error_code: str = "SCAN_DISPATCH_FAILED") -> ScanTask | None:
    """将队列派发异常收敛为可见失败状态，不保存异常正文。"""
    task = db.session.get(ScanTask, task_id)
    if task is None:
        return None
    if not is_terminal_status(task.status):
        transition_task(task, ScanTaskStatus.FAILED.value, 100)
    task.error_code = error_code
    task.error_message = None
    record_task_audit(task, "scan.failed", {"error_code": error_code})
    db.session.commit()
    return task


def record_task_audit(
    task: ScanTask,
    action: str,
    metadata: dict[str, Any],
    *,
    actor_id: int | None = None,
) -> None:
    """记录不包含源代码原文的扫描任务审计事件。"""
    db.session.add(
        AuditEvent(
            workspace_id=task.snapshot.project.workspace_id,
            actor_id=actor_id,
            action=action,
            target_type="scan_task",
            target_id=task.id,
            metadata_json=metadata,
        )
    )
