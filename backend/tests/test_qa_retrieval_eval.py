# -*- coding: utf-8 -*-
"""检索落库与离线评估测试"""
import json


def test_serialize_retrieved_docs_strips_content(app):
    from app.services.qa_retrieval_log import serialize_retrieved_docs

    docs = [
        {
            "id": "4",
            "text": "正文内容不应被落库",
            "similarity": 0.68,
            "metadata": {"title": "SQL注入", "start_line": 1, "end_line": 9},
            "source": "vector",
        }
    ]
    result = serialize_retrieved_docs(docs)
    assert result[0]["doc_id"] == "4"
    assert result[0]["title"] == "SQL注入"
    assert result[0]["start_line"] == 1
    assert "text" not in result[0]
    assert serialize_retrieved_docs(None) is None


def test_log_retrieval_persists_row(app):
    from app import db
    from app.models.qa import QaRetrievalLog
    from app.services.qa_retrieval_log import log_retrieval

    log_retrieval(
        user_id=1,
        query="什么是SQL注入",
        conversation_id=None,
        record_id=None,
        result={
            "model_name": "MiniMax-M2.7",
            "sources": [{"title": "t", "similarity": 0.5}],
            "retrieved_docs": [
                {"id": "4", "metadata": {"title": "t"}, "similarity": 0.5}
            ],
        },
        retrieval_ms=123,
    )

    row = db.session.query(QaRetrievalLog).order_by(QaRetrievalLog.id.desc()).first()
    assert row is not None
    assert row.user_id == 1
    assert row.model_name == "MiniMax-M2.7"
    assert row.retrieval_ms == 123
    docs = json.loads(row.retrieved_docs)
    assert docs[0]["doc_id"] == "4"


def test_log_retrieval_survives_invalid_result(app):
    from app import db
    from app.models.qa import QaRetrievalLog
    from app.services.qa_retrieval_log import log_retrieval

    before = db.session.query(QaRetrievalLog).count()
    # 非法 result（None retrieved_docs 等）不应抛异常
    log_retrieval(
        user_id=1,
        query="q",
        conversation_id=None,
        record_id=None,
        result={},
        retrieval_ms=0,
    )
    after = db.session.query(QaRetrievalLog).count()
    assert after >= before


def test_evaluate_empty_cases_returns_error(app):
    from app.scripts.rag_evaluate import evaluate

    report = evaluate()
    if report.get("error"):
        assert "评估集为空" in report["error"]
    else:
        assert set(report).issuperset({"cases", "hit@1", "hit@3", "hit@5", "mrr"})
