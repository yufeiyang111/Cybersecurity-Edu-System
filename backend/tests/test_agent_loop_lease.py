# -*- coding: utf-8 -*-
"""T09 LeaseService 测试：原子竞争、过期恢复、未过期不可抢占、心跳。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.loop.lease_service import LeaseService


def _make_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="租约测试",
        mode="hybrid",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_only_one_worker_acquires(app):
    with app.app_context():
        run = _make_run()
        service = LeaseService()
        assert service.acquire(run.id, "worker-a", lease_seconds=60) is True
        assert service.acquire(run.id, "worker-b", lease_seconds=60) is False
        owner, expires_at = service.current(run.id)
        assert owner == "worker-a"
        assert expires_at is not None


def test_expired_lease_can_be_recovered(app):
    with app.app_context():
        run = _make_run()
        service = LeaseService()
        assert service.acquire(run.id, "worker-a", lease_seconds=60) is True
        db.session.execute(
            db.update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(
                lease_expires_at=datetime.utcnow() - timedelta(seconds=1)
            )
        )
        db.session.commit()
        assert service.acquire(run.id, "worker-b", lease_seconds=60) is True
        owner, _ = service.current(run.id)
        assert owner == "worker-b"


def test_unexpired_lease_not_preemptible(app):
    with app.app_context():
        run = _make_run()
        service = LeaseService()
        assert service.acquire(run.id, "worker-a", lease_seconds=60) is True
        db.session.execute(
            db.update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(
                lease_expires_at=datetime.utcnow() + timedelta(seconds=30)
            )
        )
        db.session.commit()
        assert service.acquire(run.id, "worker-b", lease_seconds=60) is False


def test_refresh_extends_lease_for_owner_only(app):
    with app.app_context():
        run = _make_run()
        service = LeaseService()
        assert service.acquire(run.id, "worker-a", lease_seconds=60) is True
        assert service.refresh(run.id, "worker-a", lease_seconds=120) is True
        assert service.refresh(run.id, "worker-b", lease_seconds=120) is False


def test_release_clears_lease(app):
    with app.app_context():
        run = _make_run()
        service = LeaseService()
        assert service.acquire(run.id, "worker-a", lease_seconds=60) is True
        service.release(run.id, "worker-a")
        owner, _ = service.current(run.id)
        assert owner is None
        assert service.acquire(run.id, "worker-b", lease_seconds=60) is True


def test_heartbeat_updates_heartbeat_without_touching_lease(app):
    with app.app_context():
        run = _make_run()
        service = LeaseService()
        assert service.acquire(run.id, "worker-a", lease_seconds=60) is True
        service.heartbeat(run.id, "worker-a")
        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.heartbeat_at is not None
        owner, _ = service.current(run.id)
        assert owner == "worker-a"
