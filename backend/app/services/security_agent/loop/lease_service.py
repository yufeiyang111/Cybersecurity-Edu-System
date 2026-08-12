# -*- coding: utf-8 -*-
"""LeaseService（T09，spec §13 威胁表）：原子租约、心跳与恢复。

- acquire：原子 UPDATE（WHERE lease 为空或已过期），只有一个 Worker 能拿到；
- refresh：仅 owner 可续租（原子校验 owner 匹配）；
- release：仅 owner 可释放；
- heartbeat：刷新 heartbeat_at（长工具进度），不改变 lease 所有权。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import update

from app import db
from app.models.agent_runtime import AgentRun


class LeaseError(RuntimeError):
    """租约操作非法：非 owner 续租/释放。"""


class LeaseService:
    def acquire(self, run_id: int, owner: str, *, lease_seconds: int) -> bool:
        """尝试获取租约；成功返回 True，失败（被他人持有）返回 False。"""
        now = datetime.utcnow()
        result = db.session.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                (AgentRun.lease_expires_at.is_(None))
                | (AgentRun.lease_expires_at < now),
            )
            .values(
                lease_owner=owner,
                lease_expires_at=now + timedelta(seconds=max(1, lease_seconds)),
            )
        )
        db.session.commit()
        return result.rowcount == 1

    def refresh(self, run_id: int, owner: str, *, lease_seconds: int) -> bool:
        """仅 owner 续租；非 owner 返回 False（不抢占）。"""
        result = db.session.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.lease_owner == owner,
            )
            .values(
                lease_expires_at=datetime.utcnow()
                + timedelta(seconds=max(1, lease_seconds))
            )
        )
        db.session.commit()
        return result.rowcount == 1

    def release(self, run_id: int, owner: str) -> None:
        """仅 owner 释放租约；非 owner 抛 LeaseError。"""
        result = db.session.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.lease_owner == owner,
            )
            .values(lease_owner=None, lease_expires_at=None)
        )
        db.session.commit()
        if result.rowcount != 1:
            raise LeaseError(f"非租约持有者无法释放：run={run_id} owner={owner}")

    def heartbeat(self, run_id: int, owner: str) -> None:
        """长工具进度心跳：只刷新 heartbeat_at，不影响 lease 所有权。"""
        db.session.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.lease_owner == owner,
            )
            .values(heartbeat_at=datetime.utcnow())
        )
        db.session.commit()

    def current(self, run_id: int) -> tuple[str | None, datetime | None]:
        """返回 (lease_owner, lease_expires_at)。"""
        run = db.session.get(AgentRun, run_id)
        if run is None:
            return None, None
        return run.lease_owner, run.lease_expires_at

    def is_owner(self, run_id: int, owner: str) -> bool:
        current_owner, _ = self.current(run_id)
        return current_owner == owner
