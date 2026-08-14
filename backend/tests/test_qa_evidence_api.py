# -*- coding: utf-8 -*-
"""QA 证据详情接口的归属、预览边界与信息泄露回归测试。"""
from __future__ import annotations

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt
from app.models.knowledge import KnowledgeItem
from app.models.qa import QARecord
from app.services.rag_core.citation_evidence import (
    MAX_PREVIEW_CHARS,
    build_retrieval_signal,
)


@pytest.fixture
def qa_evidence_app(tmp_path):
    import app.models  # noqa: F401 确保 create_all 注册所有模型。
    from app.routes.qa import qa_bp

    class QAEvidenceTestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = Flask(__name__)
    application.config.from_object(QAEvidenceTestConfig)
    db.init_app(application)
    jwt.init_app(application)
    application.register_blueprint(qa_bp, url_prefix="/api/qa")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(application: Flask, user_id: int) -> dict[str, str]:
    with application.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _create_knowledge(*, title: str, content: str, status: str = "published") -> KnowledgeItem:
    item = KnowledgeItem(
        title=title,
        content=content,
        status=status,
    )
    db.session.add(item)
    db.session.flush()
    return item


def _create_record(
    *,
    user_id: int = 1,
    confidence: object = 0.8,
    manifest: object = None,
) -> QARecord:
    record = QARecord(
        user_id=user_id,
        question="测试问题",
        answer="测试回答",
        reasoning="该字段不得从证据接口返回",
        sources=[{"title": "旧来源", "doc_id": "999"}],
        confidence=confidence,
        answer_status="supported",
        citation_manifest_json=manifest,
        pipeline_version_key="rag-v2-evidence-test",
    )
    db.session.add(record)
    db.session.commit()
    return record


def _get_evidence(application: Flask, record_id: int, user_id: int = 1):
    return application.test_client().get(
        f"/api/qa/records/{record_id}/evidence",
        headers=_auth_header(application, user_id),
    )


def test_owner_receives_limited_preview_claim_coverage_and_authorized_navigation(qa_evidence_app):
    with qa_evidence_app.app_context():
        item = _create_knowledge(
            title="SQL 注入防护",
            content=(
                "# SQL 注入防护\n"
                "使用参数化查询 <b>可以</b> 区分代码与数据。\n"
                "这一整行不属于 citation 预览范围，不能泄露给前端。"
            ),
        )
        record = _create_record(
            manifest={
                "citations": [
                    {
                        "citation_id": "C-sql",
                        "document_id": str(item.id),
                        "title": item.title,
                        "title_path": "Web安全/SQL 注入",
                        "source": "公共安全知识库",
                        "start_line": 2,
                        "end_line": 2,
                        "corpus_version": "knowledge_embeddings-v1",
                    }
                ],
                "claim_citations": {
                    "主张一": ["C-sql"],
                    "主张二": ["C-sql", "C-sql"],
                },
            }
        )

        response = _get_evidence(qa_evidence_app, record.id)

    assert response.status_code == 200
    payload = response.get_json()["evidence"]
    assert payload["citation_count"] == 1
    assert payload["retrieval_signal"] == {
        "level": "high",
        "is_calibrated": False,
    }
    detail = payload["citation_details"][0]
    assert detail["citation_id"] == "C-sql"
    assert detail["claim_count"] == 2
    assert detail["document"] == {
        "type": "public_knowledge",
        "knowledge_id": item.id,
    }
    assert detail["preview"] == {
        "text": "使用参数化查询 可以 区分代码与数据。",
        "start_line": 2,
        "end_line": 2,
        "is_truncated": False,
    }
    response_text = response.get_data(as_text=True)
    assert "不得从证据接口返回" not in response_text
    assert "这一整行不属于 citation" not in response_text
    assert "doc_id" not in response_text


def test_evidence_endpoint_requires_authentication_and_record_ownership(qa_evidence_app):
    with qa_evidence_app.app_context():
        record = _create_record(manifest={"citations": [], "claim_citations": {}})
        client = qa_evidence_app.test_client()
        unauthenticated = client.get(f"/api/qa/records/{record.id}/evidence")
        other_user = client.get(
            f"/api/qa/records/{record.id}/evidence",
            headers=_auth_header(qa_evidence_app, user_id=2),
        )

    assert unauthenticated.status_code == 401
    assert other_user.status_code == 404
    assert "citation_details" not in other_user.get_data(as_text=True)


@pytest.mark.parametrize(
    "document_id,status",
    [
        ("not-a-number", "published"),
        ("999999", "published"),
        ("1", "draft"),
    ],
)
def test_invalid_missing_or_unpublished_document_never_returns_navigation_or_preview(
    qa_evidence_app,
    document_id,
    status,
):
    with qa_evidence_app.app_context():
        if document_id == "1":
            item = _create_knowledge(
                title="草稿资料",
                content="# 草稿\n不能作为公开引用预览。",
                status=status,
            )
            document_id = str(item.id)
        record = _create_record(
            manifest={
                "citations": [
                    {
                        "citation_id": "C-unavailable",
                        "document_id": document_id,
                        "title": "不可用资料",
                        "start_line": 2,
                        "end_line": 2,
                    }
                ],
                "claim_citations": {"主张": ["C-unavailable"]},
            }
        )
        response = _get_evidence(qa_evidence_app, record.id)

    assert response.status_code == 200
    detail = response.get_json()["evidence"]["citation_details"][0]
    assert detail["document"] is None
    assert detail["preview"] is None
    assert "document_id" not in detail


def test_preview_is_bounded_and_marks_truncation_without_leaking_other_lines(qa_evidence_app):
    with qa_evidence_app.app_context():
        item = _create_knowledge(
            title="长文档",
            content="# 长文档\n" + ("a" * (MAX_PREVIEW_CHARS + 60)) + "\n私密的下一行内容",
        )
        record = _create_record(
            manifest={
                "citations": [
                    {
                        "citation_id": "C-long",
                        "document_id": str(item.id),
                        "title": item.title,
                        "start_line": 2,
                        "end_line": 2,
                    }
                ],
                "claim_citations": {},
            }
        )
        response = _get_evidence(qa_evidence_app, record.id)

    preview = response.get_json()["evidence"]["citation_details"][0]["preview"]
    assert preview["is_truncated"] is True
    assert len(preview["text"]) == MAX_PREVIEW_CHARS
    assert "私密的下一行内容" not in preview["text"]


def test_malformed_manifest_and_legacy_record_return_safe_empty_details(qa_evidence_app):
    with qa_evidence_app.app_context():
        record = _create_record(confidence=None, manifest=[{"citation_id": "legacy-list"}])
        response = _get_evidence(qa_evidence_app, record.id)

    assert response.status_code == 200
    payload = response.get_json()["evidence"]
    assert payload["citation_count"] == 1
    assert payload["citation_details"] == [
        {
            "citation_id": "legacy-list",
            "title": "未命名资料",
            "title_path": None,
            "source": None,
            "start_line": None,
            "end_line": None,
            "corpus_version": None,
            "claim_count": 0,
            "document": None,
            "preview": None,
        }
    ]
    assert payload["retrieval_signal"] == {
        "level": "unavailable",
        "is_calibrated": False,
    }
    assert "旧来源" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    ("value", "expected_level"),
    [
        (1, "high"),
        (0.75, "high"),
        (0.7499, "medium"),
        (0.45, "medium"),
        (0, "low"),
        (None, "unavailable"),
        (True, "unavailable"),
        ("NaN", "unavailable"),
        (1.1, "unavailable"),
        (-0.1, "unavailable"),
    ],
)
def test_retrieval_signal_uses_safe_boundaries_and_never_claims_calibration(value, expected_level):
    signal = build_retrieval_signal(value)

    assert signal["level"] == expected_level
    assert signal["is_calibrated"] is False
