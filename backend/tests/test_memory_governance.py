# -*- coding: utf-8 -*-
"""持久记忆第二档：时间治理（过期过滤 + 强化回写）+ 反馈闭环测试。"""
from datetime import datetime, timedelta

import pytest

from app import db
from app.models.memory import MemoryFeedback, UserMemory


@pytest.fixture
def memory_app(tmp_path, monkeypatch):
    import app.models  # noqa: F401  ensure all models are registered
    from app.routes.memories import memories_bp
    from flask import Flask
    from flask_jwt_extended import JWTManager

    application = Flask(__name__)
    application.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="test-secret",
        MEMORY_TEMPORAL_DECAY_PER_DAY=0.02,
        MEMORY_FEEDBACK_SUGGEST_THRESHOLD=3,
    )
    db.init_app(application)
    JWTManager(application)
    application.register_blueprint(memories_bp, url_prefix="/api")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(memory_app, user_id: int = 1):
    from flask_jwt_extended import create_access_token

    with memory_app.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _enable_memory(user_id: int = 1) -> None:
    from app.models.user import UserPreference

    db.session.add(UserPreference(user_id=user_id, persistent_memory_enabled=True))
    db.session.commit()


def _add_memory(user_id: int, content: str, category: str = "fact", **extra) -> int:
    memory = UserMemory(user_id=user_id, content=content, category=category, **extra)
    db.session.add(memory)
    db.session.commit()
    return memory.id


def _fake_similarity(query, texts):
    return [0.95] * len(texts)


def _use_hybrid(monkeypatch):
    from app.services import secbert_embedding as embedding_module

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)


def test_retrieve_excludes_expired_memories(memory_app, monkeypatch):
    from app.services.memory import service as memory_service

    _use_hybrid(monkeypatch)
    monkeypatch.setattr(memory_service, "_last_reinforced_ts", {})
    with memory_app.app_context():
        _enable_memory()
        _add_memory(1, "用户喜欢学习密码学")
        _add_memory(
            1,
            "用户关注 Web 安全",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        results = memory_service.retrieve_for_query(
            user_id=1, query="用户喜欢什么", top_k=5
        )
        assert results
        assert all("Web 安全" not in item["content"] for item in results)


def test_retrieve_reinforces_last_reinforced_at_with_throttle(memory_app, monkeypatch):
    from app.services.memory import service as memory_service

    _use_hybrid(monkeypatch)
    monkeypatch.setattr(memory_service, "_last_reinforced_ts", {})
    with memory_app.app_context():
        _enable_memory()
        memory_id = _add_memory(1, "用户是安全工程师")

        memory_service.retrieve_for_query(user_id=1, query="用户的工作", top_k=5)
        memory = db.session.get(UserMemory, memory_id)
        first = memory.last_reinforced_at
        assert first is not None

        # 节流窗口内再次命中：不重复写库
        memory_service.retrieve_for_query(user_id=1, query="用户的工作", top_k=5)
        memory = db.session.get(UserMemory, memory_id)
        assert memory.last_reinforced_at == first


def test_feedback_submit_and_suggest_delete_threshold(memory_app):
    from app.services.memory import service as memory_service

    with memory_app.app_context():
        memory_id = _add_memory(1, "用户喜欢早起")
        for _ in range(2):
            _, negative = memory_service.submit_feedback(1, memory_id, 0)
        assert negative == 2
        assert memory_service.negative_feedback_counts(1, [memory_id]) == {memory_id: 2}

        _, negative = memory_service.submit_feedback(1, memory_id, 0)
        assert negative == 3
        assert negative >= memory_service.suggest_delete_threshold()

        # 有用反馈不计入负面
        memory_service.submit_feedback(1, memory_id, 1)
        assert memory_service.negative_feedback_counts(1, [memory_id]) == {memory_id: 3}


def test_feedback_rejects_foreign_memory(memory_app):
    from app.services.memory import service as memory_service

    with memory_app.app_context():
        memory_id = _add_memory(1, "用户 A 的私密记忆")
        memory, negative = memory_service.submit_feedback(2, memory_id, 0)
        assert memory is None
        assert negative == 0
        assert MemoryFeedback.query.count() == 0


def test_feedback_rejects_invalid_rating(memory_app):
    from app.services.memory import service as memory_service

    with memory_app.app_context():
        memory_id = _add_memory(1, "用户喜欢散步")
        with pytest.raises(ValueError):
            memory_service.submit_feedback(1, memory_id, 2)


def test_feedback_api_flow(memory_app):
    client = memory_app.test_client()
    with memory_app.app_context():
        memory_id = _add_memory(1, "用户喜欢跑步")

    response = client.post(
        f"/api/memories/{memory_id}/feedback",
        json={"rating": 0},
        headers=_auth_header(memory_app),
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["memory_id"] == memory_id
    assert payload["negative_count"] == 1
    assert payload["suggest_delete"] is False

    for _ in range(2):
        client.post(
            f"/api/memories/{memory_id}/feedback",
            json={"rating": 0},
            headers=_auth_header(memory_app),
        )
    payload = client.post(
        f"/api/memories/{memory_id}/feedback",
        json={"rating": 0},
        headers=_auth_header(memory_app),
    ).get_json()
    assert payload["negative_count"] == 4
    assert payload["suggest_delete"] is True


def test_feedback_api_rejects_invalid_rating_and_foreign_memory(memory_app):
    client = memory_app.test_client()
    with memory_app.app_context():
        memory_id = _add_memory(1, "用户喜欢徒步")

    bad = client.post(
        f"/api/memories/{memory_id}/feedback",
        json={"rating": 5},
        headers=_auth_header(memory_app),
    )
    assert bad.status_code == 400

    foreign = client.post(
        f"/api/memories/{memory_id}/feedback",
        json={"rating": 0},
        headers=_auth_header(memory_app, user_id=2),
    )
    assert foreign.status_code == 404


def test_list_marks_expired_and_suggest_delete(memory_app):
    client = memory_app.test_client()
    with memory_app.app_context():
        expired_id = _add_memory(
            1,
            "过期记忆",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        active_id = _add_memory(1, "有效记忆")
        for _ in range(3):
            db.session.add(
                MemoryFeedback(memory_id=active_id, user_id=1, rating=0)
            )
        db.session.commit()

    payload = client.get("/api/memories", headers=_auth_header(memory_app)).get_json()
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id[expired_id]["is_expired"] is True
    assert by_id[expired_id]["suggest_delete"] is False
    assert by_id[active_id]["is_expired"] is False
    assert by_id[active_id]["suggest_delete"] is True
    assert by_id[active_id]["negative_count"] == 3
