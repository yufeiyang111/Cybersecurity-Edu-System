# -*- coding: utf-8 -*-
"""持久记忆第三档：实体图谱 + Dream 后台整合测试。"""
import pytest

from app import db
from app.models.memory import MemoryDreamAudit, MemoryEntity, UserMemory


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
    )
    db.init_app(application)
    JWTManager(application)
    application.register_blueprint(memories_bp, url_prefix="/api")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


class _FakeProvider:
    def __init__(self, text: str, max_tokens: int | None = None):
        self.text = text
        self.max_tokens = max_tokens
        self.last_request = None

    def generate(self, request):
        from app.services.llm.contracts import LLMResponse

        self.last_request = request
        return LLMResponse(
            text=self.text,
            provider_name="fake",
            model="fake-model",
            status_code=200,
        )


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


# ---------- 实体抽取与入库 ----------

def test_capture_stores_entities_with_facts(memory_app, monkeypatch):
    from app.services.memory import service as memory_service

    monkeypatch.setattr(
        memory_service,
        "_selector_provider",
        lambda user_id: _FakeProvider(
            '{"facts": [{"category": "preference", "content": "用户关注 Web 安全"}], '
            '"entities": [{"name": "Web安全", "type": "tech"}, {"name": "张三", "type": "person"}]}'
        ),
    )
    with memory_app.app_context():
        _enable_memory()
        result = memory_service.capture_interaction(
            user_id=1, conversation_id=1, record_id=1, question="q", answer="a"
        )
        assert result["added"] == 1
        entities = MemoryEntity.query.all()
        assert {entity.name for entity in entities} == {"Web安全", "张三"}
        assert all(entity.memory_id is not None for entity in entities)


def test_capture_still_accepts_legacy_array_format(memory_app, monkeypatch):
    from app.services.memory import service as memory_service

    monkeypatch.setattr(
        memory_service,
        "_selector_provider",
        lambda user_id: _FakeProvider(
            '[{"category": "preference", "content": "用户喜欢简洁回答"}]'
        ),
    )
    with memory_app.app_context():
        _enable_memory()
        result = memory_service.capture_interaction(
            user_id=1, conversation_id=1, record_id=1, question="q", answer="a"
        )
        assert result["added"] == 1
        assert MemoryEntity.query.count() == 0


# ---------- 检索实体加成 ----------

def test_retrieve_entity_boost_ranks_entity_hit_first(memory_app, monkeypatch):
    from app.services.memory import service as memory_service

    _use_hybrid(monkeypatch)
    with memory_app.app_context():
        _enable_memory()
        # 两条记忆向量路同分（0.95）；实体命中"渗透测试"的记忆获得 +0.1 加成
        plain_id = _add_memory(1, "用户是安全工程师")
        entity_id = _add_memory(1, "用户最近在学习渗透测试")
        db.session.add(
            MemoryEntity(user_id=1, memory_id=entity_id, name="渗透测试", entity_type="tech")
        )
        db.session.commit()

        results = memory_service.retrieve_for_query(
            user_id=1, query="渗透测试进展如何", top_k=2
        )
        assert results
        assert results[0]["content"] == "用户最近在学习渗透测试"
        assert plain_id != entity_id


def test_entity_boost_ignores_foreign_user(memory_app, monkeypatch):
    from app.services.memory import service as memory_service

    _use_hybrid(monkeypatch)
    with memory_app.app_context():
        _enable_memory()
        memory_id = _add_memory(1, "用户是安全工程师")
        # 用户 2 的同名实体不应影响用户 1 的检索
        db.session.add(
            MemoryEntity(user_id=2, memory_id=memory_id, name="渗透测试", entity_type="tech")
        )
        db.session.commit()
        results = memory_service.retrieve_for_query(
            user_id=1, query="渗透测试进展如何", top_k=2
        )
        assert results


# ---------- Dream 后台整合 ----------

def test_dream_parse_operations():
    from app.services.memory.memory_dream import _parse_operations

    text = (
        '[{"action": "merge", "memory_ids": [1, 2], "content": "合并内容"}, '
        '{"action": "supersede", "supersede_id": 3, "content": "新事实"}, '
        '{"action": "synthesize", "memory_ids": [4, 5], "content": "概括", "category": "goal"}, '
        '{"action": "unknown", "memory_ids": [1, 2], "content": "忽略"}]'
    )
    operations = _parse_operations(text)
    assert len(operations) == 3
    assert operations[1] == {"action": "supersede", "supersede_id": 3, "content": "新事实"}
    assert operations[2]["category"] == "goal"


def test_dream_parse_rejects_invalid_operations():
    from app.services.memory.memory_dream import _parse_operations

    assert _parse_operations("not json") == []
    assert _parse_operations('[{"action": "merge", "memory_ids": [1], "content": "x"}]') == []
    assert _parse_operations('[{"action": "merge", "memory_ids": [1, 2], "content": ""}]') == []
    assert _parse_operations('[{"action": "supersede", "supersede_id": "abc", "content": "x"}]') == []


def test_dream_apply_merge_expires_old_and_creates_new(memory_app):
    from app.services.memory.memory_dream import _apply_operation

    with memory_app.app_context():
        first_id = _add_memory(1, "用户喜欢 Python")
        second_id = _add_memory(1, "用户喜欢 Python 与安全")
        _apply_operation(1, {"action": "merge", "memory_ids": [first_id, second_id], "content": "用户喜欢 Python 与安全"})

        first = db.session.get(UserMemory, first_id)
        second = db.session.get(UserMemory, second_id)
        assert first.expires_at is not None
        assert second.expires_at is not None
        assert UserMemory.query.filter(UserMemory.expires_at.is_(None)).count() == 1
        audit = MemoryDreamAudit.query.first()
        assert audit.action == "merge"
        assert str(first_id) in audit.memory_ids and str(second_id) in audit.memory_ids


def test_dream_apply_supersede_expires_old(memory_app):
    from app.services.memory.memory_dream import _apply_operation

    with memory_app.app_context():
        old_id = _add_memory(1, "用户目标是学习 Java")
        _apply_operation(1, {"action": "supersede", "supersede_id": old_id, "content": "用户目标是学习 Go"})

        old = db.session.get(UserMemory, old_id)
        assert old.expires_at is not None
        assert UserMemory.query.filter(UserMemory.expires_at.is_(None)).count() == 1


def test_dream_apply_rejects_foreign_memories(memory_app):
    from app.services.memory.memory_dream import _apply_operation

    with memory_app.app_context():
        own_id = _add_memory(1, "用户记忆")
        other_id = _add_memory(2, "他人记忆")
        with pytest.raises(ValueError):
            _apply_operation(1, {"action": "merge", "memory_ids": [own_id, other_id], "content": "合并"})
        assert MemoryDreamAudit.query.count() == 0
        assert db.session.get(UserMemory, other_id).expires_at is None


def test_dream_run_end_to_end(memory_app, monkeypatch):
    from app.services.memory import memory_dream
    from app.services.memory import service as memory_service

    provider = _FakeProvider(
        '[{"action": "merge", "memory_ids": [1, 2], "content": "用户关注网络安全"}]'
    )
    monkeypatch.setattr(memory_dream, "_selector_provider", lambda user_id: provider)
    with memory_app.app_context():
        first_id = _add_memory(1, "用户关注网络")
        second_id = _add_memory(1, "用户关注安全")
        result = memory_dream.run_dream(user_id=1)

        assert result["operations"] == 1
        assert db.session.get(UserMemory, first_id).expires_at is not None
        assert db.session.get(UserMemory, second_id).expires_at is not None
        assert MemoryDreamAudit.query.count() == 1


def test_dream_dry_run_writes_nothing(memory_app, monkeypatch):
    from app.services.memory import memory_dream

    provider = _FakeProvider(
        '[{"action": "merge", "memory_ids": [1, 2], "content": "合并内容"}]'
    )
    monkeypatch.setattr(memory_dream, "_selector_provider", lambda user_id: provider)
    with memory_app.app_context():
        first_id = _add_memory(1, "记忆一")
        second_id = _add_memory(1, "记忆二")
        result = memory_dream.run_dream(user_id=1, dry_run=True)

        assert result["operations"] == 1
        assert db.session.get(UserMemory, first_id).expires_at is None
        assert MemoryDreamAudit.query.count() == 0


def test_dream_analyze_uses_provider_max_tokens_with_sane_default(memory_app, monkeypatch):
    from app.services.memory import memory_dream

    with memory_app.app_context():
        _add_memory(1, "记忆一")
        _add_memory(1, "记忆二")

        # 未配置 max_tokens：回退默认必须足够大（推理模型思考会消耗大量 token）
        provider = _FakeProvider("[]")
        monkeypatch.setattr(memory_dream, "_selector_provider", lambda user_id: provider)
        memory_dream.run_dream(user_id=1)
        assert provider.last_request is not None
        assert provider.last_request.max_tokens >= 4096

        # 用户配置了 max_tokens：优先使用配置值
        configured = _FakeProvider("[]", max_tokens=8192)
        monkeypatch.setattr(memory_dream, "_selector_provider", lambda user_id: configured)
        memory_dream.run_dream(user_id=1)
        assert configured.last_request.max_tokens == 8192


# ---------- Dream API（浏览器入口） ----------

def test_dream_api_requires_auth_and_runs(memory_app, monkeypatch):
    from app.services.memory import memory_dream

    provider = _FakeProvider(
        '[{"action": "merge", "memory_ids": [1, 2], "content": "用户关注网络安全"}]'
    )
    monkeypatch.setattr(memory_dream, "_selector_provider", lambda user_id: provider)
    client = memory_app.test_client()

    unauth = client.post("/api/memories/dream", json={"dry_run": False})
    assert unauth.status_code == 401

    with memory_app.app_context():
        first_id = _add_memory(1, "用户关注网络")
        second_id = _add_memory(1, "用户关注安全")

    response = client.post(
        "/api/memories/dream",
        json={"dry_run": False},
        headers=_auth_header(memory_app),
    )
    assert response.status_code == 200
    assert response.get_json()["operations"] == 1
    with memory_app.app_context():
        assert db.session.get(UserMemory, first_id).expires_at is not None
        assert MemoryDreamAudit.query.count() == 1


def test_dream_audits_api_is_user_scoped(memory_app, monkeypatch):
    from app.services.memory import memory_dream

    provider = _FakeProvider(
        '[{"action": "merge", "memory_ids": [1, 2], "content": "合并内容"}]'
    )
    monkeypatch.setattr(memory_dream, "_selector_provider", lambda user_id: provider)
    client = memory_app.test_client()
    with memory_app.app_context():
        first_id = _add_memory(1, "用户一记忆")
        second_id = _add_memory(1, "用户一记忆二")
        memory_dream.run_dream(user_id=1)

    mine = client.get("/api/memories/dream/audits", headers=_auth_header(memory_app)).get_json()
    assert len(mine["items"]) == 1
    assert mine["items"][0]["action"] == "merge"

    other = client.get("/api/memories/dream/audits", headers=_auth_header(memory_app, user_id=2)).get_json()
    assert other["items"] == []
