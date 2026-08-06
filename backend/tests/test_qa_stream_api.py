"""问答流式端点 /api/qa/ask/stream 集成测试（真实 qa 蓝图 + 内存库 + mock 引擎）"""
from __future__ import annotations

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt


class _FakeStreamEngine:
    def ask_stream(self, query, conversation_history, user_preferences=None, memories=None):
        yield {"type": "delta", "content": "\u4f60\u597d"}
        yield {"type": "reasoning", "delta": "\u601d\u8003\u4e2d"}
        yield {
            "type": "done",
            "answer": "\u4f60\u597d\uff0c\u4e16\u754c",
            "reasoning": "\u601d\u8003\u4e2d",
            "sources": [],
            "confidence": 0.8,
            "response_time": 1.2,
            "warning_code": None,
            "retrieved_docs": [],
            "rag_warnings": ["knowledge-9:ignore_instructions"],
        }


class _BoomEngine:
    def ask_stream(self, query, conversation_history, user_preferences=None, memories=None):
        raise RuntimeError("secret internal detail must not leak")


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


def test_ask_stream_requires_authentication(qa_app):
    client = qa_app.test_client()

    resp = client.post("/api/qa/ask/stream", json={"question": "x"})

    assert resp.status_code == 401


def test_ask_stream_rejects_empty_question(qa_app):
    client = qa_app.test_client()

    resp = client.post(
        "/api/qa/ask/stream",
        json={"question": "   "},
        headers=_auth_header(qa_app),
    )

    assert resp.status_code == 400


def test_ask_stream_emits_sse_events_and_persists_record(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeStreamEngine())
    client = qa_app.test_client()

    resp = client.post(
        "/api/qa/ask/stream",
        json={"question": "\u4ec0\u4e48\u662fSQL\u6ce8\u5165"},
        headers=_auth_header(qa_app),
    )

    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    assert resp.headers.get("Cache-Control") == "no-cache"

    text = resp.get_data(as_text=True)
    assert "event: delta\ndata: {\"delta\": \"\u4f60\u597d\"}" in text
    assert "event: reasoning\ndata: {\"delta\": \"\u601d\u8003\u4e2d\"}" in text
    assert "event: done" in text
    assert "\u4f60\u597d\uff0c\u4e16\u754c" in text
    assert '"confidence": 0.8' in text
    assert '"response_time": 1.2' in text
    assert '"rag_warnings": ["knowledge-9:ignore_instructions"]' in text

    from app.models.qa import QARecord

    records = QARecord.query.all()
    assert len(records) == 1
    assert records[0].answer == "\u4f60\u597d\uff0c\u4e16\u754c"
    assert records[0].confidence == 0.8


def test_ask_stream_error_event_does_not_leak_internals(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _BoomEngine())
    client = qa_app.test_client()

    resp = client.post(
        "/api/qa/ask/stream",
        json={"question": "x"},
        headers=_auth_header(qa_app),
    )

    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "event: error" in text
    assert "secret internal detail" not in text
