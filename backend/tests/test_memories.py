"""Persistent user memory: extraction, storage, retrieval, and API tests."""
from __future__ import annotations

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt


class _FakeProvider:
    """Returns canned JSON facts regardless of the request."""

    def __init__(self, text: str):
        self.text = text

    def generate(self, request):
        from app.services.llm.contracts import LLMResponse

        return LLMResponse(
            text=self.text,
            provider_name="fake",
            model="fake-model",
            status_code=200,
        )


@pytest.fixture
def memory_app(tmp_path, monkeypatch):
    import app.models  # noqa: F401  ensure all models are registered
    from app.routes.memories import memories_bp

    class MemoryTestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    application = Flask(__name__)
    application.config.from_object(MemoryTestConfig)
    db.init_app(application)
    jwt.init_app(application)
    application.register_blueprint(memories_bp, url_prefix="/api")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(memory_app, user_id: int = 1):
    with memory_app.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _enable_memory(user_id: int = 1) -> None:
    from app.models.user import UserPreference

    preferences = UserPreference(user_id=user_id, persistent_memory_enabled=True)
    db.session.add(preferences)
    db.session.commit()


def _add_memory(user_id: int, content: str, category: str = "fact") -> int:
    from app.models.memory import UserMemory

    memory = UserMemory(user_id=user_id, content=content, category=category)
    db.session.add(memory)
    db.session.commit()
    return memory.id


def test_memory_enabled_defaults_to_false(memory_app):
    from app.services.memory.service import memory_enabled

    with memory_app.app_context():
        assert memory_enabled(1) is False


def test_capture_interaction_skipped_when_disabled(memory_app, monkeypatch):
    from app.models.memory import UserMemory
    from app.services.memory import service as memory_service

    monkeypatch.setattr(memory_service, "_selector_provider", lambda user_id: _FakeProvider('[{"category": "preference", "content": "用户关注 Web 安全"}]'))
    with memory_app.app_context():
        result = memory_service.capture_interaction(
            user_id=1,
            conversation_id=7,
            record_id=3,
            question="x",
            answer="y",
        )
        assert result["added"] == 0
        assert UserMemory.query.count() == 0


def test_capture_interaction_stores_extracted_facts(memory_app, monkeypatch):
    from app.models.memory import UserMemory
    from app.services.memory import service as memory_service

    monkeypatch.setattr(
        memory_service,
        "_selector_provider",
        lambda user_id: _FakeProvider(
            '[{"category": "preference", "content": "用户偏好简洁回答"}, {"category": "goal", "content": "用户目标是学习渗透测试"}]'
        ),
    )
    with memory_app.app_context():
        _enable_memory()
        from app.services.memory import service as memory_service

        assert memory_service.memory_enabled(1) is True
        result = memory_service.capture_interaction(
            user_id=1,
            conversation_id=7,
            record_id=3,
            question="如何学习渗透测试？",
            answer="建议从基础开始...",
        )
        assert result["added"] == 2
        assert result["skipped"] == 0
        memories = UserMemory.query.filter_by(user_id=1).all()
        assert len(memories) == 2
        assert memories[0].source_conversation_id == 7
        assert memories[0].source_record_id == 3


def test_retrieve_for_query_returns_relevant_memories(memory_app, monkeypatch):
    from app.services import secbert_embedding as embedding_module
    from app.services.memory import service as memory_service

    # 用确定性相似度替代真实 embedding（真实模型/宿主内存波动会让该断言不稳定）
    def fake_similarity(query, texts):
        return [1.0 if "Web" in text or "安全" in text else 0.0 for text in texts]

    monkeypatch.setattr(embedding_module, "compute_text_similarity", fake_similarity)

    _enable_memory()
    with memory_app.app_context():
        _add_memory(1, "用户是安全工程师，关注 Web 安全")
        _add_memory(1, "用户喜欢学习密码学")
        results = memory_service.retrieve_for_query(user_id=1, query="用户关注什么安全方向")
        assert results
        assert any("Web 安全" in item["content"] for item in results)


def test_retrieve_for_query_skipped_when_disabled(memory_app):
    from app.services.memory import service as memory_service

    with memory_app.app_context():
        _add_memory(1, "用户是安全工程师")
        assert memory_service.retrieve_for_query(user_id=1, query="用户是谁") == []


def test_delete_memory_is_user_scoped(memory_app):
    from app.models.memory import UserMemory
    from app.services.memory import service as memory_service

    with memory_app.app_context():
        owner_id = _add_memory(1, "用户 A 的记忆")
        other_id = _add_memory(2, "用户 B 的记忆")
        assert memory_service.delete_memory(1, other_id) is False
        assert UserMemory.query.count() == 2
        assert memory_service.delete_memory(1, owner_id) is True
        assert UserMemory.query.count() == 1


def test_memories_api_requires_auth(memory_app):
    response = memory_app.test_client().get("/api/memories")
    assert response.status_code == 401


def test_memories_api_list_and_delete(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app)
    with memory_app.app_context():
        memory_id = _add_memory(1, "用户是安全工程师", "fact")

    listed = client.get("/api/memories", headers=headers)
    assert listed.status_code == 200
    assert listed.json["total"] == 1
    assert listed.json["items"][0]["content"] == "用户是安全工程师"
    assert listed.json["items"][0]["category_label"] == "事实"

    deleted = client.delete(f"/api/memories/{memory_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json == {"deleted": True}

    listed_after = client.get("/api/memories", headers=headers)
    assert listed_after.json["total"] == 0


def test_memories_api_delete_other_user_returns_404(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app, user_id=1)
    with memory_app.app_context():
        memory_id = _add_memory(2, "别人的记忆")

    deleted = client.delete(f"/api/memories/{memory_id}", headers=headers)
    assert deleted.status_code == 404


def test_memories_api_create(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app)

    created = client.post("/api/memories", json={"content": "用户是后端工程师", "category": "fact"}, headers=headers)
    assert created.status_code == 201
    assert created.json["content"] == "用户是后端工程师"
    assert created.json["category"] == "fact"
    assert created.json["category_label"] == "事实"
    assert created.json["user_id"] == 1

    listed = client.get("/api/memories", headers=headers)
    assert listed.json["total"] == 1
    assert listed.json["items"][0]["content"] == "用户是后端工程师"


def test_memories_api_create_validations(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app)

    missing = client.post("/api/memories", json={"category": "fact"}, headers=headers)
    assert missing.status_code == 400

    blank = client.post("/api/memories", json={"content": "   ", "category": "fact"}, headers=headers)
    assert blank.status_code == 400

    bad_category = client.post("/api/memories", json={"content": "x", "category": "unknown"}, headers=headers)
    assert bad_category.status_code == 400

    too_long = client.post("/api/memories", json={"content": "x" * 2001, "category": "fact"}, headers=headers)
    assert too_long.status_code == 400


def test_memories_api_create_defaults_category_and_requires_auth(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app)

    created = client.post("/api/memories", json={"content": "默认分类"}, headers=headers)
    assert created.status_code == 201
    assert created.json["category"] == "fact"

    unauthorized = client.post("/api/memories", json={"content": "x"})
    assert unauthorized.status_code == 401


def test_memories_api_update(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app)
    with memory_app.app_context():
        memory_id = _add_memory(1, "旧内容", "fact")

    updated = client.put(f"/api/memories/{memory_id}", json={"content": "新内容", "category": "goal"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json["content"] == "新内容"
    assert updated.json["category"] == "goal"
    assert updated.json["category_label"] == "目标"

    listed = client.get("/api/memories", headers=headers)
    assert listed.json["total"] == 1
    assert listed.json["items"][0]["content"] == "新内容"


def test_memories_api_update_other_user_returns_404(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app, user_id=1)
    with memory_app.app_context():
        memory_id = _add_memory(2, "别人的记忆")

    updated = client.put(f"/api/memories/{memory_id}", json={"content": "篡改", "category": "fact"}, headers=headers)
    assert updated.status_code == 404


def test_memories_api_update_invalid_returns_400(memory_app):
    client = memory_app.test_client()
    headers = _auth_header(memory_app)
    with memory_app.app_context():
        memory_id = _add_memory(1, "内容", "fact")

    blank = client.put(f"/api/memories/{memory_id}", json={"content": "", "category": "fact"}, headers=headers)
    assert blank.status_code == 400

    bad_category = client.put(f"/api/memories/{memory_id}", json={"content": "x", "category": "nope"}, headers=headers)
    assert bad_category.status_code == 400


def test_parse_facts_json_tolerates_markdown_fences():
    from app.services.memory.extractor import parse_facts_json

    assert parse_facts_json("```json\n[{\"category\": \"fact\", \"content\": \"a\"}]\n```") == [
        {"category": "fact", "content": "a"}
    ]
    assert parse_facts_json("不是 JSON") == []
    assert parse_facts_json("[]") == []


def test_heuristic_facts_extracts_explicit_preferences():
    from app.services.memory.extractor import _heuristic_facts

    assert _heuristic_facts("我喜欢简洁直接的回答") == [
        {"category": "preference", "content": "用户喜欢简洁直接的回答"}
    ]
    assert _heuristic_facts("请记住我早上七点起床开始巡检安全日志") == [
        {"category": "preference", "content": "用户早上七点起床开始巡检安全日志"}
    ]
    assert _heuristic_facts("我是安全运营工程师") == [
        {"category": "fact", "content": "用户是安全运营工程师"}
    ]
    assert _heuristic_facts("我决定使用 PostgreSQL 作为主库") == [
        {"category": "decision", "content": "用户决定使用 PostgreSQL 作为主库"}
    ]
    assert _heuristic_facts("我打算下半年学习云原生安全") == [
        {"category": "goal", "content": "用户打算下半年学习云原生安全"}
    ]
    assert _heuristic_facts("什么是SQL注入攻击？") == []


def test_extract_facts_falls_back_to_heuristic(memory_app, monkeypatch):
    from app.services.memory import extractor
    from app.services.memory.extractor import extract_facts

    class _BoomProvider:
        def generate(self, request):
            raise RuntimeError("provider down")

    class _NoSleep:
        @staticmethod
        def sleep(seconds):
            return None

    monkeypatch.setattr(extractor, "time", _NoSleep)
    facts = extract_facts(_BoomProvider(), "我喜欢简洁的回答", "好的")
    assert facts == [{"category": "preference", "content": "用户喜欢简洁的回答"}]
