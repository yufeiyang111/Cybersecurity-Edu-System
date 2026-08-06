"""QA rag_warnings 持久化与序列化测试（Phase 6.1 RAG 治理结果前端展示）"""
from __future__ import annotations

import pathlib

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt


class _FakeStreamEngine:
    def ask_stream(self, query, conversation_history, user_preferences=None, memories=None):
        yield {
            "type": "done",
            "answer": "\u4f60\u597d\uff0c\u4e16\u754c",
            "reasoning": "",
            "sources": [],
            "confidence": 0.8,
            "response_time": 1.2,
            "warning_code": None,
            "retrieved_docs": [],
            "rag_warnings": ["knowledge-9:ignore_instructions", "doc-4:reveal_prompt"],
        }


@pytest.fixture
def qa_app(tmp_path):
    import app.models  # noqa: F401  ensure all models are registered for create_all
    from app.routes.qa import qa_bp

    class QATestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = Flask(__name__)
    application.config.from_object(QATestConfig)
    db.init_app(application)
    jwt.init_app(application)
    application.register_blueprint(qa_bp, url_prefix="/api/qa")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(qa_app):
    with qa_app.app_context():
        token = create_access_token(identity="1")
    return {"Authorization": f"Bearer {token}"}


def _create_record(qa_app, rag_warnings=None):
    from app.models.qa import QARecord
    from app.routes.qa import _save_qa_record

    result = {
        "answer": "\u6d4b\u8bd5\u56de\u7b54",
        "sources": [],
        "confidence": 0.7,
        "model_name": "test",
        "response_time": 1.0,
    }
    if rag_warnings is not None:
        result["rag_warnings"] = rag_warnings
    return _save_qa_record(1, None, "\u6d4b\u8bd5\u95ee\u9898", result, [])


def test_save_qa_record_persists_rag_warnings(qa_app):
    from app.models.qa import QARecord

    record = _create_record(qa_app, rag_warnings=["doc-1:ignore_instructions"])
    reloaded = db.session.get(QARecord, record.id)

    assert reloaded is not None
    assert reloaded.rag_warnings == ["doc-1:ignore_instructions"]


def test_save_qa_record_defaults_to_none_without_rag_warnings(qa_app):
    from app.models.qa import QARecord

    record = _create_record(qa_app)
    reloaded = db.session.get(QARecord, record.id)

    assert reloaded is not None
    assert reloaded.rag_warnings is None


def test_ask_stream_persists_rag_warnings_to_record(qa_app, monkeypatch):
    from app.models.qa import QARecord
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeStreamEngine())
    client = qa_app.test_client()

    resp = client.post(
        "/api/qa/ask/stream",
        json={"question": "\u4ec0\u4e48\u662fSQL\u6ce8\u5165"},
        headers=_auth_header(qa_app),
    )

    assert resp.status_code == 200
    records = QARecord.query.all()
    assert len(records) == 1
    assert records[0].rag_warnings == [
        "knowledge-9:ignore_instructions",
        "doc-4:reveal_prompt",
    ]


def test_get_record_returns_rag_warnings(qa_app):
    record = _create_record(qa_app, rag_warnings=["doc-4:reveal_prompt"])
    client = qa_app.test_client()

    resp = client.get(f"/api/qa/{record.id}", headers=_auth_header(qa_app))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["record"]["rag_warnings"] == ["doc-4:reveal_prompt"]


def test_get_conversation_records_include_rag_warnings(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeStreamEngine())
    client = qa_app.test_client()

    conv_resp = client.post(
        "/api/qa/conversations",
        json={"title": "\u6d4b\u8bd5"},
        headers=_auth_header(qa_app),
    )
    assert conv_resp.status_code == 201
    conversation_id = conv_resp.get_json()["conversation"]["id"]

    ask_resp = client.post(
        "/api/qa/ask/stream",
        json={"question": "x", "conversation_id": conversation_id},
        headers=_auth_header(qa_app),
    )
    assert ask_resp.status_code == 200

    detail = client.get(
        f"/api/qa/conversations/{conversation_id}",
        headers=_auth_header(qa_app),
    )
    assert detail.status_code == 200
    records = detail.get_json()["conversation"]["records"]
    assert len(records) == 1
    assert records[0]["rag_warnings"] == [
        "knowledge-9:ignore_instructions",
        "doc-4:reveal_prompt",
    ]


def test_migration_and_init_sql_contain_rag_warnings_column(qa_app):
    repository_root = pathlib.Path(__file__).resolve().parents[2]

    migration_sql = (repository_root / "database" / "migrations" / "008_qa_rag_warnings.sql").read_text(
        encoding="utf-8"
    )
    init_sql = (repository_root / "database" / "init.sql").read_text(encoding="utf-8")

    assert "rag_warnings" in migration_sql
    assert "ALTER TABLE qa_records" in migration_sql
    assert "rag_warnings JSON NULL" in init_sql
