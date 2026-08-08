# -*- coding: utf-8 -*-
"""Agent run RQ dispatch tests: queue path and in-process fallback."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app import db
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.models.security import ProjectSnapshot, SecurityProject, Workspace
from app.services.security_agent.runner import run_queued_agent_run


@pytest.fixture
def rq_dispatch_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """App with RQ dispatch enabled and a fake Redis instance."""
    import app.models
    from app import create_app

    from tests.conftest import _install_legacy_route_stubs

    _install_legacy_route_stubs(monkeypatch)

    config = type(
        "RQDispatchTestConfig",
        (object,),
        {
            "APP_ENV": "testing",
            "DEBUG": False,
            "TESTING": True,
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'rq_dispatch.db'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
            "CORS_ALLOWED_ORIGINS": ["https://security.example.test"],
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "app.log"),
            "AGENT_LOG_FILE": str(tmp_path / "logs" / "agent.log"),
            "AGENT_RUN_EXECUTOR": "rq",
            "AGENT_MIN_STEP_INTERVAL_SECONDS": 0,
            "RQ_ASYNC": True,
            "REDIS_URL": "redis://localhost:6379/0",
            "RQ_QUEUE_NAME": "cyberguard-agent-test",
            "ARCHIVE_MAX_UPLOAD_BYTES": 50 * 1024 * 1024,
            "ARCHIVE_MAX_EXTRACT_BYTES": 500 * 1024 * 1024,
            "ARCHIVE_MAX_FILES": 20_000,
            "ARCHIVE_MAX_DEPTH": 10,
        },
    )
    application = create_app(config)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _make_run(application, tmp_path: Path) -> int:
    with application.app_context():
        workspace = Workspace(name="ws", slug="ws")
        db.session.add(workspace)
        db.session.flush()
        project = SecurityProject(workspace_id=workspace.id, name="proj", created_by=1)
        db.session.add(project)
        db.session.flush()
        snapshot_dir = tmp_path / "snap"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "app.py").write_text("x = 1\n", encoding="utf-8")
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="sha",
            storage_path=str(snapshot_dir),
            file_count=1,
            total_bytes=5,
        )
        db.session.add(snapshot)
        db.session.flush()
        run = AgentRun(
            workspace_id=workspace.id,
            project_id=project.id,
            snapshot_id=snapshot.id,
            created_by=1,
            goal_text="g",
            mode="baseline",
            status=AgentRunStatus.QUEUED.value,
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id
        # 使用 file-backed sqlite 时其他线程可共享连接；刷新状态保证测试可重入。
        db.session.remove()
        return run_id


def _wait_terminal(application, run_id: int) -> AgentRun:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with application.app_context():
            run = AgentRun.query.get(run_id)
            status = run.status.value if hasattr(run.status, "value") else str(run.status)
            if status in {"completed", "completed_with_warnings", "partial", "failed", "canceled"}:
                return run
        time.sleep(0.1)
    raise AssertionError("agent run did not reach a terminal status in time")


def test_dispatch_enqueues_with_fake_redis(rq_dispatch_app, tmp_path, monkeypatch):
    application = rq_dispatch_app
    run_id = _make_run(application, tmp_path)

    import fakeredis
    import redis as redis_lib
    from app.services.security_agent.service import AgentRunService
    from rq import Queue

    fake = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(redis_lib.Redis, "from_url", staticmethod(lambda url: fake))

    with application.app_context():
        run = AgentRun.query.get(run_id)
        AgentRunService()._dispatch(run, "trace-1")

    queue = Queue("cyberguard-agent-test", connection=fake)
    assert queue.count == 1

    job = queue.fetch_job(queue.job_ids[0])
    assert job.func_name == "app.services.security_agent.runner.run_queued_agent_run"
    assert job.args == (run_id, "trace-1")


def test_run_queued_agent_run_completes_open_run(rq_dispatch_app, tmp_path, monkeypatch):
    application = rq_dispatch_app
    run_id = _make_run(application, tmp_path)

    import app as app_module
    from app.services.security_agent.runner import run_queued_agent_run

    # RQ worker 进程内 create_app() 本应读取真实配置；测试中用固定 app 隔离。
    monkeypatch.setattr(app_module, "create_app", lambda: application)

    run_queued_agent_run(run_id, "trace-2")

    with application.app_context():
        run = AgentRun.query.get(run_id)
        assert run.status.value in {"completed", "completed_with_warnings"}


def test_dispatch_falls_back_to_thread_when_redis_down(rq_dispatch_app, tmp_path, monkeypatch):
    application = rq_dispatch_app
    run_id = _make_run(application, tmp_path)

    import redis as redis_lib
    from app.services.security_agent.service import AgentRunService
    from redis.exceptions import ConnectionError as RedisConnectionError

    def raise_connection(*args, **kwargs):
        raise RedisConnectionError("Connection refused")

    monkeypatch.setattr(redis_lib.Redis, "from_url", staticmethod(raise_connection))

    with application.app_context():
        run = AgentRun.query.get(run_id)
        # Executor is "rq"; enqueue raises; dispatch must not propagate and
        # must start a thread that completes the run.
        AgentRunService()._dispatch(run, "trace-3")

    run = _wait_terminal(application, run_id)
    assert run.status.value in {"completed", "completed_with_warnings"}