# -*- coding: utf-8 -*-
"""持久记忆写入去重（context lookup）测试。

去重依赖向量相似度，测试必须 monkeypatch compute_text_similarity，
禁止发真实 embedding 请求（与 test_memories.py 同一隔离原则）。
"""
import pytest

from app import db
from app.models.memory import UserMemory


@pytest.fixture
def memory_app(tmp_path, monkeypatch):
    from flask import Flask
    from flask_jwt_extended import JWTManager
    from app import db

    application = Flask(__name__)
    application.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="test-secret",
        MEMORY_DEDUP_THRESHOLD=0.92,
    )
    db.init_app(application)
    JWTManager(application)
    with application.app_context():
        db.create_all()
        yield application


def _add_memory(user_id: int, content: str, category: str = "fact") -> int:
    memory = UserMemory(user_id=user_id, content=content, category=category)
    db.session.add(memory)
    db.session.commit()
    return memory.id


def _fake_similarity(query, texts):
    """确定性相似度：完全相同为 1.0，包含关系 0.95，无关 0.1。"""
    return [
        1.0 if text == query else (0.95 if query in text or text in query else 0.1)
        for text in texts
    ]


def test_dedup_skips_identical_fact(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        _add_memory(1, "用户负责公司安全运营")
        kept, skipped = memory_service._dedup_against_existing(
            1, [{"content": "用户负责公司安全运营", "category": "fact"}]
        )
        assert skipped == 1
        assert kept == []


def test_dedup_keeps_distinct_facts(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        _add_memory(1, "用户负责公司安全运营")
        kept, skipped = memory_service._dedup_against_existing(
            1,
            [
                {"content": "用户喜欢学习密码学", "category": "preference"},
                {"content": "用户负责公司安全运营", "category": "fact"},
            ],
        )
        assert skipped == 1
        assert len(kept) == 1
        assert kept[0]["content"] == "用户喜欢学习密码学"


def test_dedup_is_user_scoped(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        _add_memory(1, "用户负责公司安全运营")
        # 用户 2 无既有记忆，同类内容不应被用户 1 的记忆拦截
        kept, skipped = memory_service._dedup_against_existing(
            2, [{"content": "用户负责公司安全运营", "category": "fact"}]
        )
        assert skipped == 0
        assert len(kept) == 1


def test_dedup_keeps_all_when_embedding_fails(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    def boom(query, texts):
        raise RuntimeError("embedder down")

    monkeypatch.setattr(embedding_module, "compute_text_similarity", boom)
    with memory_app.app_context():
        _add_memory(1, "用户负责公司安全运营")
        kept, skipped = memory_service._dedup_against_existing(
            1, [{"content": "用户负责公司安全运营", "category": "fact"}]
        )
        # 降级不阻塞入库，避免静默丢数据
        assert skipped == 0
        assert len(kept) == 1


def test_dedup_empty_existing_keeps_all(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        kept, skipped = memory_service._dedup_against_existing(
            1, [{"content": "新记忆", "category": "fact"}]
        )
        assert skipped == 0
        assert len(kept) == 1


def test_capture_interaction_dedups(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    monkeypatch.setattr(memory_service, "_selector_provider", lambda user_id: object())
    monkeypatch.setattr(
        memory_service,
        "_extract",
        lambda provider, q, a: [
            {"category": "fact", "content": "用户负责公司安全运营"}
        ],
    )
    from app.models.user import UserPreference

    with memory_app.app_context():
        pref = UserPreference(user_id=1, persistent_memory_enabled=True)
        db.session.add(pref)
        _add_memory(1, "用户负责公司安全运营")
        db.session.commit()

        result = memory_service.capture_interaction(
            user_id=1,
            conversation_id=7,
            record_id=3,
            question="x",
            answer="y",
        )
        assert result["added"] == 0
        assert result["skipped"] == 1
        assert UserMemory.query.count() == 1
