"""会话详情分页接口 /api/qa/conversations/<id> 集成测试（真实 qa 蓝图 + 内存库）"""
from __future__ import annotations

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt
from app.models.qa import QAConversation, QARecord


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


def _make_conversation_with_records(qa_app, user_id=1, count=7):
    with qa_app.app_context():
        conv = QAConversation(user_id=user_id, title="分页测试")
        db.session.add(conv)
        db.session.flush()
        for i in range(count):
            db.session.add(QARecord(
                conversation_id=conv.id,
                user_id=user_id,
                question=f"问题{i + 1}",
                answer=f"回答{i + 1}"
            ))
        db.session.commit()
        return conv.id


def test_requires_authentication(qa_app):
    conv_id = _make_conversation_with_records(qa_app)
    resp = qa_app.test_client().get(f"/api/qa/conversations/{conv_id}?page=1&per_page=3")
    assert resp.status_code == 401


def test_without_paging_returns_all_records(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=7)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["conversation"]["records"]) == 7
    assert body["conversation"]["record_count"] == 7
    assert "record_meta" not in body
    # 正序：第一条是最早的问题
    assert body["conversation"]["records"][0]["question"] == "问题1"
    assert body["conversation"]["records"][-1]["question"] == "问题7"


def test_paging_returns_page_and_meta(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=7)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?page=2&per_page=3",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert [r["question"] for r in body["conversation"]["records"]] == ["问题4", "问题5", "问题6"]
    assert body["conversation"]["record_count"] == 7
    assert body["record_meta"] == {
        "page": 2,
        "per_page": 3,
        "total": 7,
        "pages": 3
    }


def test_page_minus_one_returns_last_page(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=7)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?page=-1&per_page=3",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert [r["question"] for r in body["conversation"]["records"]] == ["问题7"]
    assert body["record_meta"]["page"] == 3


def test_page_minus_one_with_exact_multiple_returns_full_last_page(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=6)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?page=-1&per_page=3",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert [r["question"] for r in body["conversation"]["records"]] == ["问题4", "问题5", "问题6"]
    assert body["record_meta"]["page"] == 2


def test_page_beyond_range_returns_empty_records(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=4)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?page=99&per_page=3",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["conversation"]["records"] == []
    assert body["record_meta"]["page"] == 99


def test_cursor_returns_recent_messages(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=7)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?limit=3",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    # 最近 3 条（正序）
    assert [r["question"] for r in body["conversation"]["records"]] == ["问题5", "问题6", "问题7"]
    assert body["record_meta"]["total"] == 7
    assert body["record_meta"]["returned"] == 3
    assert body["record_meta"]["has_more"] is True


def test_cursor_with_before_id_returns_earlier_messages(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=7)
    first_page = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?limit=3",
        headers=_auth_header(qa_app),
    ).get_json()
    first_record_id = first_page["conversation"]["records"][0]["id"]
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?limit=3&before_id={first_record_id}",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert [r["question"] for r in body["conversation"]["records"]] == ["问题2", "问题3", "问题4"]
    assert body["record_meta"]["has_more"] is True


def test_cursor_before_id_reaches_beginning(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=7)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?limit=3&before_id=3",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert [r["question"] for r in body["conversation"]["records"]] == ["问题1", "问题2"]
    assert body["record_meta"]["has_more"] is False


def test_cursor_limit_larger_than_total_returns_all(qa_app):
    conv_id = _make_conversation_with_records(qa_app, count=4)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?limit=10",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["conversation"]["records"]) == 4
    assert body["record_meta"]["has_more"] is False


def test_paging_does_not_leak_other_users_conversation(qa_app):
    conv_id = _make_conversation_with_records(qa_app, user_id=2, count=3)
    resp = qa_app.test_client().get(
        f"/api/qa/conversations/{conv_id}?page=1&per_page=2",
        headers=_auth_header(qa_app),
    )
    assert resp.status_code == 404
