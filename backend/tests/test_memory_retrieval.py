# -*- coding: utf-8 -*-
"""持久记忆混合检索（向量 + 词法 RRF 融合 + 时间加权）测试。

检索依赖 embedding，测试必须 monkeypatch compute_text_similarity，
禁止发真实 embedding/LLM 请求。
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
        MEMORY_TEMPORAL_DECAY_PER_DAY=0.02,
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


def _enable_memory(user_id: int = 1) -> None:
    from app.models.user import UserPreference

    pref = UserPreference(user_id=user_id, persistent_memory_enabled=True)
    db.session.add(pref)
    db.session.commit()


def _fake_similarity(query, texts):
    """确定性向量路：包含关键词得高分，其余低分（低于 MIN_SIMILARITY=0.30）。"""
    return [0.95 if ("安全" in text or "Web" in text) else 0.1 for text in texts]


def test_hybrid_retrieval_ranks_lexical_hit_first(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    # 向量路：两条都命中关键词（0.95）；词法路：内容完全包含 query 词条的排前
    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        _enable_memory()
        _add_memory(1, "用户喜欢学习密码学与密码分析")
        _add_memory(1, "用户是安全工程师，关注 Web 安全")
        results = memory_service.retrieve_for_query(
            user_id=1, query="用户关注什么安全方向", top_k=5
        )
        assert results
        assert results[0]["content"] == "用户是安全工程师，关注 Web 安全"


def test_lexical_only_when_embedding_fails(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    def boom(query, texts):
        raise RuntimeError("embedder down")

    monkeypatch.setattr(embedding_module, "compute_text_similarity", boom)
    with memory_app.app_context():
        _enable_memory()
        _add_memory(1, "用户负责公司安全运营")
        _add_memory(1, "用户喜欢学习密码学")
        results = memory_service.retrieve_for_query(
            user_id=1, query="公司安全运营", top_k=5
        )
        # 降级路走纯词法：词法命中记忆必须返回，且不抛异常
        assert results
        assert any("安全运营" in item["content"] for item in results)


def test_min_similarity_still_filters_vector_path(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        _enable_memory()
        _add_memory(1, "今天天气很好适合散步")
        # 无词法命中 + 向量低分：不应返回任何记忆
        results = memory_service.retrieve_for_query(
            user_id=1, query="完全不相关的另一个话题", top_k=5
        )
        assert results == []


def test_retrieve_skipped_when_disabled(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    monkeypatch.setattr(embedding_module, "compute_text_similarity", _fake_similarity)
    with memory_app.app_context():
        _add_memory(1, "用户是安全工程师")
        assert memory_service.retrieve_for_query(user_id=1, query="用户是谁") == []


def test_conversation_boosting_still_works(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    def fake_sim(query, texts):
        return [0.95] * len(texts)

    monkeypatch.setattr(embedding_module, "compute_text_similarity", fake_sim)
    with memory_app.app_context():
        _enable_memory()
        other_id = _add_memory(1, "用户负责公司安全运营")
        # 同会话来源记忆（source_conversation_id=9）应排在无来源之前
        same_conv = UserMemory(
            user_id=1,
            content="用户是安全运营工程师",
            source_conversation_id=9,
        )
        db.session.add(same_conv)
        db.session.commit()

        results = memory_service.retrieve_for_query(
            user_id=1, query="用户的工作", conversation_id=9, top_k=5
        )
        assert results
        assert results[0]["content"] == "用户是安全运营工程师"
