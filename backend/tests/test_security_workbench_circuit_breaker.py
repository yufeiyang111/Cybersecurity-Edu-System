# -*- coding: utf-8 -*-
"""安全工作台熔断开关与接口防护测试。"""
import pytest
from flask import Flask
from flask_jwt_extended import create_access_token
from pathlib import Path

from app import create_app, db
from app.config import Config
from app.models.user import User


class EnabledConfig:
    APP_ENV = "testing"
    DEBUG = False
    TESTING = True
    SECRET_KEY = "a" * 32
    JWT_SECRET_KEY = "b" * 32
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ALLOWED_ORIGINS = ["https://security.example.test"]
    SECURITY_WORKSPACE_ROOT = "security-workspaces"
    SECURITY_WORKBENCH_ENABLED = True
    REDIS_URL = ""
    RQ_QUEUE_NAME = "cyberguard-security-test"
    RQ_ASYNC = False
    UPLOAD_FOLDER = "uploads"
    LOG_FILE = "logs/test.log"
    AGENT_LOG_FILE = "logs/agent.log"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
    }


class DisabledConfig(EnabledConfig):
    SECURITY_WORKBENCH_ENABLED = False


def _create_test_app(config_class, tmp_path: Path) -> Flask:
    cfg = type(
        "DynamicTestConfig",
        (config_class,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "security-workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "AGENT_LOG_FILE": str(tmp_path / "logs" / "agent.log"),
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'circuit_breaker.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
            "AGENT_RUN_EXECUTOR": "synchronous",
            "AGENT_MIN_STEP_INTERVAL_SECONDS": 0,
            "RQ_ASYNC": False,
        },
    )
    application = create_app(cfg)
    return application


def test_circuit_breaker_blocks_security_routes_when_disabled(tmp_path: Path):
    """当 SECURITY_WORKBENCH_ENABLED=False 时，所有 /api/security/* 接口直接熔断返回 503。"""
    app = _create_test_app(DisabledConfig, tmp_path)
    with app.app_context():
        db.create_all()
        user = User(username="testuser", email="test@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))

    client = app.test_client()
    headers = {"Authorization": f"Bearer {token}"}

    # 测试项目列表接口
    res1 = client.get("/api/security/projects", headers=headers)
    assert res1.status_code == 503
    data1 = res1.get_json()
    assert data1["code"] == "FEATURE_DISABLED"
    assert "熔断" in data1["error"] or "下线" in data1["error"]

    # 测试概览接口
    res2 = client.get("/api/security/workbench/overview", headers=headers)
    assert res2.status_code == 503
    assert res2.get_json()["code"] == "FEATURE_DISABLED"

    # 测试未登录请求，熔断层也先于业务逻辑返回 503
    res3 = client.get("/api/security/projects")
    assert res3.status_code == 503
    assert res3.get_json()["code"] == "FEATURE_DISABLED"


def test_security_routes_accessible_when_enabled(tmp_path: Path):
    """当 SECURITY_WORKBENCH_ENABLED=True 时，接口正常走业务鉴权与处理。"""
    app = _create_test_app(EnabledConfig, tmp_path)
    with app.app_context():
        db.create_all()
        user = User(username="normaluser", email="normal@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))

    client = app.test_client()
    headers = {"Authorization": f"Bearer {token}"}

    # 正常请求返回 200 业务响应（不为 503 FEATURE_DISABLED）
    res = client.get("/api/security/projects", headers=headers)
    assert res.status_code == 200
    assert "items" in res.get_json()


def test_user_activity_handles_disabled_security_workbench(tmp_path: Path):
    """当安全工作台熔断时，用户活跃统计接口仍正常返回（tasks 置空）。"""
    app = _create_test_app(DisabledConfig, tmp_path)
    with app.app_context():
        db.create_all()
        user = User(username="actuser", email="act@example.com", password_hash="x")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))

    client = app.test_client()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/user/activity", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "qa" in data
    assert data["tasks"] == []


def test_config_validation_for_security_workbench_enabled():
    """验证 Config 对 SECURITY_WORKBENCH_ENABLED 布尔配置的校验。"""
    class ValidConfig(Config):
        APP_ENV = "testing"
        SECRET_KEY = "x" * 32
        JWT_SECRET_KEY = "y" * 32
        SECURITY_WORKBENCH_ENABLED = False
        CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

    # 应该正常通过校验无异常
    Config.validate_security_settings(ValidConfig)

    class InvalidConfig(Config):
        APP_ENV = "testing"
        SECRET_KEY = "x" * 32
        JWT_SECRET_KEY = "y" * 32
        SECURITY_WORKBENCH_ENABLED = "not-a-bool"
        CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

    with pytest.raises(ValueError, match="SECURITY_WORKBENCH_ENABLED must be a boolean"):
        Config.validate_security_settings(InvalidConfig)
