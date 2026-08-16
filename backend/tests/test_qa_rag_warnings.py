# -*- coding: utf-8 -*-
"""QA rag_warnings 持久化与序列化测试（Phase 6.1 RAG 治理结果前端展示）"""
from __future__ import annotations

import json

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
            "answer_status": "supported",
            "citations": {"citations": [{"citation_id": "C-stream"}]},
            "trace_id": 77,
            "pipeline_version": "rag-v2-stream",
            "retrieval_summary": {"candidate_count": 5},
        }


class _FakeV2Engine:
    def ask(self, query, conversation_history, user_preferences=None, memories=None):
        return {
            "answer": "带结构化字段的回答",
            "reasoning": "当前用户可访问的原始 reasoning",
            "retrieved_docs": [{"title": "来源"}],
            "confidence": 0.8,
            "model_name": "test-model",
            "response_time": 0.2,
            "answer_status": "supported",
            "citations": {"citations": [{"citation_id": "C-ask"}]},
            "trace_id": 78,
            "pipeline_version": "rag-v2-ask",
            "retrieval_summary": {"candidate_count": 5},
        }


class _FailingEngine:
    def ask(self, query, conversation_history, user_preferences=None, memories=None):
        raise RuntimeError("provider-secret=should-not-reach-client")


class _BrokenStreamEngine:
    def ask_stream(self, query, conversation_history, user_preferences=None, memories=None):
        raise RuntimeError("provider details must not be exposed")
        yield  # pragma: no cover - 保持生成器协议


class _MissingCitationStreamEngine:
    def ask_stream(self, query, conversation_history, user_preferences=None, memories=None):
        yield {
            "type": "done",
            "answer": "不应继续标记为 supported",
            "reasoning": "",
            "sources": [],
            "answer_status": "supported",
            "pipeline_version": "rag-v2-missing-citation",
            "retrieval_summary": {
                "request_id": "request-missing-citation",
                "query_fingerprint": "d" * 64,
                "pipeline_version_key": "rag-v2-missing-citation",
                "stage_summary": {"candidate_count": 1},
            },
        }


class _FakeTraceV2Engine:
    def ask(self, query, conversation_history, user_preferences=None, memories=None):
        return {
            "answer": "可追溯回答",
            "reasoning": "当前记录的原始 reasoning",
            "retrieved_docs": [{"title": "来源"}],
            "confidence": 0.8,
            "model_name": "test-model",
            "response_time": 0.2,
            "answer_status": "supported",
            "citations": {"citations": [{"citation_id": "C-trace"}]},
            "pipeline_version": "rag-v2-trace-test",
            "retrieval_summary": {
                "request_id": "request-trace-test",
                "query_fingerprint": "c" * 64,
                "pipeline_version_key": "rag-v2-trace-test",
                "stage_summary": {
                    "candidate_count": 5,
                    "query": "不得保存的用户问题",
                },
                "warnings": ["TOKEN_COUNT_ESTIMATED"],
                "retrieval_ms": 13,
            },
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


def _auth_header(qa_app, user_id=1):
    with qa_app.app_context():
        token = create_access_token(identity=str(user_id))
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


def test_save_qa_record_persists_reasoning(qa_app):
    """思考过程必须随记录落库，重新加载会话时回显（推理模型长思考内容用 MEDIUMTEXT 存储）。"""
    from app.models.qa import QARecord
    from app.routes.qa import _save_qa_record

    long_reasoning = "先分析攻击面" + "详细推理过程" * 500
    result = {
        "answer": "测试回答",
        "reasoning": long_reasoning,
        "sources": [],
        "confidence": 0.7,
        "model_name": "test",
        "response_time": 1.0,
    }
    record = _save_qa_record(1, None, "测试问题", result, [])
    reloaded = db.session.get(QARecord, record.id)

    assert reloaded is not None
    assert reloaded.reasoning == long_reasoning
    assert len(reloaded.reasoning) > 1000


def test_qa_record_to_dict_includes_reasoning(qa_app):
    from app.models.qa import QARecord
    from app.routes.qa import _save_qa_record

    result = {
        "answer": "测试回答",
        "reasoning": "思考过程内容",
        "sources": [],
        "confidence": 0.7,
        "model_name": "test",
        "response_time": 1.0,
    }
    record = _save_qa_record(1, None, "测试问题", result, [])

    data = record.to_dict()
    assert data["reasoning"] == "思考过程内容"


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


def test_save_qa_record_persists_rag_core_fields_without_breaking_legacy_fields(qa_app):
    from app.models.qa import QARecord
    from app.routes.qa import _save_qa_record

    result = {
        "answer": "带引用的回答",
        "reasoning": "仅当前记录用户可见的原始 reasoning",
        "sources": [{"title": "来源"}],
        "confidence": 0.8,
        "model_name": "test-model",
        "response_time": 0.2,
        "rag_warnings": ["TOKEN_COUNT_ESTIMATED"],
        "answer_status": "supported",
        "citations": {
            "citations": [{"citation_id": "C-test", "document_id": "doc-1"}],
            "claim_citations": {"主张": ["C-test"]},
        },
        "trace_id": 42,
        "pipeline_version": "rag-v2-test",
    }

    record = _save_qa_record(1, None, "测试问题", result, [])
    reloaded = db.session.get(QARecord, record.id)

    assert reloaded.answer == "带引用的回答"
    assert reloaded.reasoning == "仅当前记录用户可见的原始 reasoning"
    assert reloaded.answer_status == "supported"
    assert reloaded.citation_manifest_json == result["citations"]
    assert reloaded.rag_trace_id == 42
    assert reloaded.pipeline_version_key == "rag-v2-test"
    payload = reloaded.to_dict()
    assert payload["citations"] == result["citations"]
    assert payload["pipeline_version"] == "rag-v2-test"

def test_save_qa_record_discards_malformed_rag_core_metadata(qa_app):
    from app.models.qa import QARecord
    from app.routes.qa import _save_qa_record

    record = _save_qa_record(
        1,
        None,
        "测试问题",
        {
            "answer": "回答",
            "sources": [],
            "answer_status": "unknown-status",
            "citations": "not-json-manifest",
            "trace_id": True,
            "pipeline_version": "   ",
        },
        [],
    )
    reloaded = db.session.get(QARecord, record.id)

    assert reloaded.answer_status is None
    assert reloaded.citation_manifest_json is None
    assert reloaded.rag_trace_id is None
    assert reloaded.pipeline_version_key is None


def test_ask_returns_v2_metadata_without_removing_legacy_fields(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeV2Engine())
    response = qa_app.test_client().post(
        "/api/qa/ask",
        json={"question": "什么是 SQL 注入"},
        headers=_auth_header(qa_app),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["answer"] == "带结构化字段的回答"
    assert payload["reasoning"] == "当前用户可访问的原始 reasoning"
    assert payload["sources"] == [{"title": "来源"}]
    assert payload["answer_status"] == "supported"
    assert payload["citations"] == {"citations": [{"citation_id": "C-ask"}]}
    assert payload["trace_id"] == 78
    assert payload["pipeline_version"] == "rag-v2-ask"
    assert payload["retrieval_summary"] == {"candidate_count": 5}


def test_ask_stream_done_event_contains_v2_metadata(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeStreamEngine())
    response = qa_app.test_client().post(
        "/api/qa/ask/stream",
        json={"question": "什么是 SQL 注入"},
        headers=_auth_header(qa_app),
    )

    assert response.status_code == 200
    events = response.data.decode("utf-8").split("\n\n")
    done_event = next(event for event in events if event.startswith("event: done"))
    done_payload = json.loads(done_event.split("data: ", 1)[1])
    assert done_payload["answer_status"] == "supported"
    assert done_payload["citations"] == {"citations": [{"citation_id": "C-stream"}]}
    assert done_payload["trace_id"] == 77
    assert done_payload["pipeline_version"] == "rag-v2-stream"
    assert done_payload["retrieval_summary"] == {"candidate_count": 5}


def test_ask_hides_provider_exception_details(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FailingEngine())
    response = qa_app.test_client().post(
        "/api/qa/ask",
        json={"question": "触发失败"},
        headers=_auth_header(qa_app),
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"] == "生成答案失败，请稍后重试。"
    assert "provider-secret" not in json.dumps(payload, ensure_ascii=False)


def test_reasoning_is_visible_to_owner_and_hidden_from_other_user(qa_app):
    from app.routes.qa import _save_qa_record

    record = _save_qa_record(
        1,
        None,
        "测试问题",
        {
            "answer": "回答",
            "reasoning": "只允许记录所有者查看的原始 CoT",
            "sources": [],
        },
        [],
    )
    client = qa_app.test_client()

    owner_response = client.get(
        f"/api/qa/{record.id}",
        headers=_auth_header(qa_app, user_id=1),
    )
    other_response = client.get(
        f"/api/qa/{record.id}",
        headers=_auth_header(qa_app, user_id=2),
    )

    assert owner_response.status_code == 200
    assert owner_response.get_json()["record"]["reasoning"] == "只允许记录所有者查看的原始 CoT"
    assert other_response.status_code == 404
    assert "只允许记录所有者查看的原始 CoT" not in other_response.get_data(as_text=True)

@pytest.mark.parametrize(
    "answer_status",
    ["insufficient_evidence", "conflicting_evidence"],
)
def test_save_qa_record_preserves_all_rag_core_answer_statuses(qa_app, answer_status):
    from app.models.qa import QARecord
    from app.routes.qa import _save_qa_record

    record = _save_qa_record(
        1,
        None,
        "测试问题",
        {
            "answer": "回答",
            "sources": [],
            "answer_status": answer_status,
        },
        [],
    )

    assert db.session.get(QARecord, record.id).answer_status == answer_status

def test_ask_persists_redacted_trace_and_replaces_response_trace_id(qa_app, monkeypatch):
    from app.models.qa import QARecord, RagPipelineVersion, RagRetrievalTrace
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeTraceV2Engine())
    response = qa_app.test_client().post(
        "/api/qa/ask",
        json={"question": "什么是 SQL 注入"},
        headers=_auth_header(qa_app),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload["trace_id"], int)
    assert payload["trace_id"] > 0

    record = db.session.get(QARecord, payload["id"])
    trace = db.session.get(RagRetrievalTrace, payload["trace_id"])
    assert record.rag_trace_id == trace.id
    assert trace.record_id == record.id
    assert trace.stage_summary_json == {"candidate_count": 5}
    assert "不得保存" not in json.dumps(trace.stage_summary_json, ensure_ascii=False)
    assert trace.pipeline_version_id is not None
    assert RagPipelineVersion.query.filter_by(version_key="rag-v2-trace-test").count() == 1


def test_trace_persistence_failure_does_not_block_answer(qa_app, monkeypatch):
    from app.models.qa import QARecord
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _FakeTraceV2Engine())
    monkeypatch.setattr(
        qa_module,
        "persist_trace_for_qa_record",
        lambda **kwargs: None,
    )
    response = qa_app.test_client().post(
        "/api/qa/ask",
        json={"question": "什么是 SQL 注入"},
        headers=_auth_header(qa_app),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["answer"] == "可追溯回答"
    assert payload["trace_id"] is None
    assert db.session.get(QARecord, payload["id"]).rag_trace_id is None

def test_stream_interruption_marks_event_degraded_without_leaking_exception(qa_app, monkeypatch):
    from app.routes import qa as qa_module

    monkeypatch.setattr(qa_module, "get_rag_engine", lambda: _BrokenStreamEngine())
    response = qa_app.test_client().post(
        "/api/qa/ask/stream",
        json={"question": "触发中断"},
        headers=_auth_header(qa_app),
    )

    assert response.status_code == 200
    response_text = response.get_data(as_text=True)
    done_event = next(
        event
        for event in response_text.split("\n\n")
        if event.startswith("event: done")
    )
    payload = json.loads(done_event.split("data: ", 1)[1])
    assert payload["answer_status"] == "degraded"
    assert payload["warning_code"] == "RAG_STREAM_INTERRUPTED"
    assert payload["rag_warnings"] == ["RAG_STREAM_INTERRUPTED"]
    assert payload["citations"]["citations"] == []
    assert "event: error" not in response_text
    assert "provider details" not in json.dumps(payload, ensure_ascii=False)


def test_stream_missing_v2_manifest_is_degraded_instead_of_claiming_supported(qa_app, monkeypatch):
    from app.models.qa import QARecord
    from app.routes import qa as qa_module

    monkeypatch.setattr(
        qa_module,
        "get_rag_engine",
        lambda: _MissingCitationStreamEngine(),
    )
    response = qa_app.test_client().post(
        "/api/qa/ask/stream",
        json={"question": "缺失引用"},
        headers=_auth_header(qa_app),
    )

    done_event = next(
        event
        for event in response.get_data(as_text=True).split("\n\n")
        if event.startswith("event: done")
    )
    payload = json.loads(done_event.split("data: ", 1)[1])
    record = db.session.get(QARecord, payload["id"])
    assert payload["answer_status"] == "degraded"
    assert payload["citations"] is None
    assert record.answer_status == "degraded"

def test_evidence_endpoint_only_returns_owner_safe_manifest_without_reasoning(qa_app):
    from app.routes.qa import _save_qa_record

    record = _save_qa_record(
        1,
        None,
        "测试问题",
        {
            "answer": "回答正文",
            "reasoning": "不能由 evidence 接口返回的原始 CoT",
            "sources": [{"title": "旧来源"}],
            "answer_status": "supported",
            "citations": {
                "citations": [{"citation_id": "C-evidence", "document_id": "doc-1"}],
                "claim_citations": {"主张": ["C-evidence"]},
            },
            "pipeline_version": "rag-v2-evidence",
        },
        [],
    )
    client = qa_app.test_client()

    unauthenticated = client.get(f"/api/qa/records/{record.id}/evidence")
    owner = client.get(
        f"/api/qa/records/{record.id}/evidence",
        headers=_auth_header(qa_app, user_id=1),
    )
    other_user = client.get(
        f"/api/qa/records/{record.id}/evidence",
        headers=_auth_header(qa_app, user_id=2),
    )

    assert unauthenticated.status_code == 401
    assert owner.status_code == 200
    payload = owner.get_json()["evidence"]
    assert payload["record_id"] == record.id
    assert payload["answer_status"] == "supported"
    assert payload["citations"]["citations"][0]["citation_id"] == "C-evidence"
    assert payload["pipeline_version"] == "rag-v2-evidence"
    assert "reasoning" not in payload
    assert "answer" not in payload
    assert "sources" not in payload
    assert other_user.status_code == 404
