# -*- coding: utf-8 -*-
"""用户活跃统计接口 /api/user/activity 集成测试（真实蓝图 + 内存库）"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt
from app.models.qa import QARecord
from app.models.security import (
    Workspace,
    WorkspaceMember,
    SecurityProject,
    ProjectSnapshot,
    ScanTask,
)
from app.models.agent_runtime import AgentRun, AgentRunMode


@pytest.fixture
def activity_app(tmp_path):
    import app.models  # noqa: F401  ensure all models are registered for create_all
    from app.routes.user_activity import user_activity_bp

    class ActivityTestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = Flask(__name__)
    application.config.from_object(ActivityTestConfig)
    db.init_app(application)
    jwt.init_app(application)
    application.register_blueprint(user_activity_bp, url_prefix="/api/user")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(app, user_id=1):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _make_qa_record(user_id=1, days_ago=1, count=1):
    for _ in range(count):
        db.session.add(QARecord(
            user_id=user_id,
            question="测试问题",
            answer="测试回答",
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        ))
    db.session.commit()


def _make_workspace(user_id=1, name="默认工作区"):
    ws = Workspace(name=name, slug=name)
    db.session.add(ws)
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=user_id))
    db.session.commit()
    return ws


def _make_project_and_snapshot(workspace_id):
    project = SecurityProject(workspace_id=workspace_id, name="测试项目")
    db.session.add(project)
    db.session.flush()
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="github",
        content_sha256="a" * 64,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def _make_agent_run(workspace_id, snapshot, days_ago=1, count=1):
    for _ in range(count):
        db.session.add(AgentRun(
            workspace_id=workspace_id,
            project_id=snapshot.project_id,
            snapshot_id=snapshot.id,
            goal_text="测试目标",
            mode=AgentRunMode.BASELINE.value,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        ))
    db.session.commit()


def _make_scan_task(snapshot, days_ago=1, count=1):
    for _ in range(count):
        db.session.add(ScanTask(
            snapshot_id=snapshot.id,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        ))
    db.session.commit()


def test_requires_authentication(activity_app):
    resp = activity_app.test_client().get("/api/user/activity")
    assert resp.status_code == 401


def test_empty_returns_empty_series(activity_app):
    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app)
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["qa"] == []
    assert body["tasks"] == []


def test_qa_records_grouped_by_day(activity_app):
    _make_qa_record(user_id=1, days_ago=1, count=3)
    _make_qa_record(user_id=1, days_ago=3, count=2)

    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app)
    )
    body = resp.get_json()

    by_day = {item["date"]: item["count"] for item in body["qa"]}
    assert len(by_day) == 2
    day_1 = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    day_3 = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    assert by_day[day_1] == 3
    assert by_day[day_3] == 2


def test_qa_records_isolated_by_user(activity_app):
    _make_qa_record(user_id=1, days_ago=1, count=5)
    _make_qa_record(user_id=2, days_ago=1, count=9)

    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app, user_id=2)
    )
    body = resp.get_json()
    total = sum(item["count"] for item in body["qa"])
    assert total == 9


def test_qa_outside_window_ignored(activity_app):
    _make_qa_record(user_id=1, days_ago=1, count=1)
    _make_qa_record(user_id=1, days_ago=400, count=1)

    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app)
    )
    body = resp.get_json()
    total = sum(item["count"] for item in body["qa"])
    assert total == 1


def test_tasks_merge_agent_and_scan(activity_app):
    ws = _make_workspace(user_id=1)
    snapshot = _make_project_and_snapshot(ws.id)
    _make_agent_run(ws.id, snapshot, days_ago=1, count=2)
    _make_scan_task(snapshot, days_ago=1, count=1)
    _make_scan_task(snapshot, days_ago=2, count=1)

    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app)
    )
    body = resp.get_json()

    by_day = {item["date"]: item["count"] for item in body["tasks"]}
    day_1 = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    day_2 = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")
    assert by_day[day_1] == 3
    assert by_day[day_2] == 1


def test_tasks_isolated_by_workspace(activity_app):
    ws_a = _make_workspace(user_id=1, name="A")
    snapshot_a = _make_project_and_snapshot(ws_a.id)
    _make_agent_run(ws_a.id, snapshot_a, days_ago=1, count=4)

    ws_b = _make_workspace(user_id=2, name="B")
    snapshot_b = _make_project_and_snapshot(ws_b.id)
    _make_agent_run(ws_b.id, snapshot_b, days_ago=1, count=7)

    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app, user_id=1)
    )
    body = resp.get_json()
    total = sum(item["count"] for item in body["tasks"])
    assert total == 4


def test_tasks_without_membership_empty(activity_app):
    _make_workspace(user_id=1, name="A")
    resp = activity_app.test_client().get(
        "/api/user/activity", headers=_auth_header(activity_app, user_id=3)
    )
    body = resp.get_json()
    assert body["tasks"] == []
