# -*- coding: utf-8 -*-
"""管理后台用户详情接口 /api/admin/users/<id>/detail 集成测试"""
from __future__ import annotations

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt
from app.models.user import User, Role, LoginLog
from app.models.qa import QARecord, QAConversation, Favorite


@pytest.fixture
def admin_users_app(tmp_path):
    import app.models  # noqa: F401  ensure all models are registered for create_all
    from app.routes.admin_users import admin_users_bp

    class AdminUsersTestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = Flask(__name__)
    application.config.from_object(AdminUsersTestConfig)
    db.init_app(application)
    jwt.init_app(application)
    application.register_blueprint(admin_users_bp, url_prefix="/api/admin")

    with application.app_context():
        db.create_all()
        admin_role = Role(name="admin")
        user_role = Role(name="user")
        db.session.add_all([admin_role, user_role])
        db.session.commit()

        admin_user = User(username="boss", nickname="管理员", role=admin_role, is_active=True)
        db.session.add(admin_user)
        db.session.flush()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(app, user_id=1, role="admin"):
    with app.app_context():
        token = create_access_token(
            identity=str(user_id),
            additional_claims={"role": role},
        )
    return {"Authorization": f"Bearer {token}"}


def _make_user(app, username="alice", nickname="小爱", role_name="user"):
    with app.app_context():
        role = Role.query.filter_by(name=role_name).one()
        user = User(username=username, nickname=nickname, role=role, is_active=True)
        db.session.add(user)
        db.session.flush()
        user_id = user.id

        for i in range(3):
            db.session.add(QARecord(
                user_id=user_id,
                question=f"问题{i}",
                answer="回答",
            ))
        db.session.add(QAConversation(user_id=user_id, title="会话"))
        db.session.flush()
        db.session.add(Favorite(user_id=user_id, qa_record_id=1))
        db.session.add(LoginLog(user_id=user_id, ip_address="127.0.0.1", status="success"))
        db.session.commit()
        return user_id


def test_requires_authentication(admin_users_app):
    resp = admin_users_app.test_client().get("/api/admin/users/1/detail")
    assert resp.status_code == 401


def test_non_admin_forbidden(admin_users_app):
    user_id = _make_user(admin_users_app)
    resp = admin_users_app.test_client().get(
        f"/api/admin/users/{user_id}/detail",
        headers=_auth_header(admin_users_app, role="user"),
    )
    assert resp.status_code == 403


def test_not_found(admin_users_app):
    resp = admin_users_app.test_client().get(
        "/api/admin/users/999/detail",
        headers=_auth_header(admin_users_app),
    )
    assert resp.status_code == 404


def test_detail_returns_user_and_stats(admin_users_app):
    user_id = _make_user(admin_users_app)
    resp = admin_users_app.test_client().get(
        f"/api/admin/users/{user_id}/detail",
        headers=_auth_header(admin_users_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["user"]["username"] == "alice"
    assert body["user"]["nickname"] == "小爱"
    assert body["user"]["role"] == "user"
    assert body["user"]["is_active"] is True

    assert body["stats"]["qa_count"] == 3
    assert body["stats"]["conversation_count"] == 1
    assert body["stats"]["favorite_count"] == 1

    assert len(body["login_logs"]) == 1
    assert body["login_logs"][0]["ip_address"] == "127.0.0.1"
    assert body["login_logs"][0]["status"] == "success"

    assert len(body["recent_records"]) == 3
    assert body["recent_records"][0]["question"] == "问题0"
