# -*- coding: utf-8 -*-
"""RAG 脱敏 trace 与评测运行管理员接口的授权/最小化返回测试。"""
from __future__ import annotations

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from app import db, jwt
from app.config import Config
from app.models.qa import RagEvaluationRun, RagPipelineVersion, RagRetrievalTrace
from app.services.observability import (
    get_rag_runtime_metrics,
    register_rag_runtime_metrics,
)


@pytest.fixture
def admin_rag_app(tmp_path):
    import app.models  # noqa: F401 让全部关联模型注册到 SQLAlchemy metadata
    from app.routes.admin_rag import admin_rag_bp

    class AdminRagTestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        RAG_METRICS_SAMPLE_LIMIT = 16

    application = Flask(__name__)
    application.config.from_object(AdminRagTestConfig)
    db.init_app(application)
    jwt.init_app(application)
    register_rag_runtime_metrics(application)
    application.register_blueprint(admin_rag_bp, url_prefix="/api/admin")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _auth_header(app, *, user_id: int = 1, role: str = "admin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(user_id),
            additional_claims={"role": role},
        )
    return {"Authorization": f"Bearer {token}"}


def _seed_trace_and_run() -> tuple[int, int]:
    pipeline = RagPipelineVersion(
        version_key="rag-v2-test",
        config_json={"top_k": 5},
        prompt_version="citation-v1",
        embedding_version="test-embedding",
        reranker_version="test-reranker",
    )
    db.session.add(pipeline)
    db.session.flush()

    trace = RagRetrievalTrace(
        request_id="req-test-1",
        user_id=17,
        pipeline_version_id=pipeline.id,
        query_fingerprint="a" * 64,
        stage_summary_json={
            "candidate": {
                "candidate_count": 8,
                "retrieval_paths": {
                    "dense_only": 2,
                    "bm25_only": 1,
                    "both": 5,
                },
                "candidates": [
                    {
                        "document_id": "99",
                        "content": "候选正文不能返回",
                    },
                ],
            },
            "rerank": {
                "status": "completed",
                "input_count": 8,
                "output_count": 5,
                "elapsed_ms": 6,
            },
            "evidence": {
                "answer_status": "supported",
                "reference_count": 3,
                "token_count": 160,
                "token_budget": 400,
                "rejection_counts": {
                    "prompt_injection": 1,
                },
            },
            "answer": {
                "answer_status": "supported",
                "citation_count": 3,
                "claim_count": 2,
            },
            "query": "该字段即使脏数据存在也不能返回",
            "nested": {"prompt": "不能返回"},
        },
        warnings_json=["TOKEN_COUNT_ESTIMATED"],
        retrieval_ms=27,
    )
    run = RagEvaluationRun(
        pipeline_version_id=pipeline.id,
        corpus_version="knowledge_embeddings-v1",
        status="completed",
        metrics_json={"recall_at_20": 0.8},
        report_path="D:/internal/rag_report.json",
    )
    db.session.add_all([trace, run])
    db.session.commit()
    return trace.id, run.id


def test_admin_rag_endpoints_require_authentication(admin_rag_app):
    client = admin_rag_app.test_client()

    assert client.get("/api/admin/rag/traces/1").status_code == 401
    assert client.get("/api/admin/rag/evaluation-runs").status_code == 401
    assert client.get("/api/admin/rag/runtime-metrics").status_code == 401


def test_non_admin_cannot_read_trace_or_evaluation_runs(admin_rag_app):
    with admin_rag_app.app_context():
        trace_id, _ = _seed_trace_and_run()
    client = admin_rag_app.test_client()
    headers = _auth_header(admin_rag_app, role="user")

    assert client.get(f"/api/admin/rag/traces/{trace_id}", headers=headers).status_code == 403
    assert client.get("/api/admin/rag/evaluation-runs", headers=headers).status_code == 403
    assert client.get("/api/admin/rag/runtime-metrics", headers=headers).status_code == 403


def test_admin_trace_response_is_redacted_even_for_legacy_dirty_rows(admin_rag_app):
    with admin_rag_app.app_context():
        trace_id, _ = _seed_trace_and_run()
    client = admin_rag_app.test_client()

    response = client.get(
        f"/api/admin/rag/traces/{trace_id}",
        headers=_auth_header(admin_rag_app),
    )

    assert response.status_code == 200
    trace = response.get_json()["trace"]
    assert trace["id"] == trace_id
    assert trace["stage_summary"] == {
        "candidate": {
            "candidate_count": 8,
            "retrieval_paths": {
                "dense_only": 2,
                "bm25_only": 1,
                "both": 5,
            },
        },
        "rerank": {
            "status": "completed",
            "input_count": 8,
            "output_count": 5,
            "elapsed_ms": 6,
        },
        "evidence": {
            "answer_status": "supported",
            "reference_count": 3,
            "token_count": 160,
            "token_budget": 400,
            "rejection_counts": {
                "prompt_injection": 1,
            },
        },
        "answer": {
            "answer_status": "supported",
            "citation_count": 3,
            "claim_count": 2,
        },
    }
    serialized = str(trace)
    assert "query" not in trace["stage_summary"]
    assert "'prompt':" not in serialized
    assert "document_id" not in serialized
    assert "候选正文不能返回" not in serialized
    assert "query_fingerprint" not in trace
    assert "request_id" not in trace
    assert "record_id" not in trace
    assert "user_id" not in trace


def test_admin_evaluation_runs_are_paginated_and_do_not_expose_report_path(admin_rag_app):
    with admin_rag_app.app_context():
        _, run_id = _seed_trace_and_run()
    client = admin_rag_app.test_client()

    response = client.get(
        "/api/admin/rag/evaluation-runs?page=1&per_page=1",
        headers=_auth_header(admin_rag_app),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["per_page"] == 1
    assert payload["runs"][0]["id"] == run_id
    assert payload["runs"][0]["metrics"]["recall_at_20"] == 0.8
    assert "report_path" not in payload["runs"][0]


def test_admin_runtime_metrics_expose_only_allowed_aggregate_fields(
    admin_rag_app,
    monkeypatch,
):
    monkeypatch.setattr(Config, "RAG_DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(Config, "RAG_PIPELINE_V2_ENABLED", True)
    monkeypatch.setattr(Config, "RAG_STRICT_CITATIONS", True)
    monkeypatch.setattr(Config, "RAG_METRICS_SAMPLE_LIMIT", 16)
    raw_query = "raw query must not be returned by admin metrics"

    with admin_rag_app.app_context():
        metrics = get_rag_runtime_metrics()
        assert metrics is not None
        metrics.record_execution(
            pipeline_mode="v2",
            pipeline_version="rag-v2-0123456789abcdef01234567",
            answer_status="degraded",
            warnings=("QDRANT_UNAVAILABLE", raw_query),
            stage_durations_ms={
                "candidate": 7,
                "retrieval_total": 9,
            },
        )

    response = admin_rag_app.test_client().get(
        "/api/admin/rag/runtime-metrics",
        headers=_auth_header(admin_rag_app),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["runtime"] == {
        "pipeline_mode": "v2",
        "pipeline_v2_enabled": True,
        "strict_citations_enabled": True,
        "diagnostics_enabled": True,
        "metrics_sample_limit": 16,
    }
    series = payload["metrics"]["series"][0]
    serialized = str(payload)
    assert payload["metrics"]["scope"] == "process"
    assert payload["metrics"]["sample_limit"] == 16
    assert series["component_events"]["qdrant"]["failed"] == 1
    assert series["durations_ms"]["candidate"]["p50"] == 7
    assert raw_query not in serialized
    assert "request_id" not in serialized
    assert "document_id" not in serialized


def test_admin_runtime_metrics_returns_not_found_when_diagnostics_disabled(
    admin_rag_app,
    monkeypatch,
):
    monkeypatch.setattr(Config, "RAG_DIAGNOSTICS_ENABLED", False)

    response = admin_rag_app.test_client().get(
        "/api/admin/rag/runtime-metrics",
        headers=_auth_header(admin_rag_app),
    )

    assert response.status_code == 404
