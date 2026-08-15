# -*- coding: utf-8 -*-
"""Enterprise RAG Core 加性迁移、模型契约与 legacy QA 兼容测试。"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.dialects import mysql
from sqlalchemy.exc import ProgrammingError

from app.models.qa import (
    QARecord,
    RagEvaluationResult,
    RagEvaluationRun,
    RagEvalCase,
    RagPipelineVersion,
    RagRetrievalTrace,
)
from app.scripts.apply_sql_migration import MIGRATION_IDS

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BACKEND_ROOT / "database" / "migrations"
INIT_SQL = BACKEND_ROOT / "database" / "init.sql"
MIGRATION_ID = "038_enterprise_rag_core"


def test_enterprise_rag_migration_is_registered_last_and_additive():
    path = MIGRATIONS_DIR / f"{MIGRATION_ID}.sql"
    content = path.read_text(encoding="utf-8")

    assert MIGRATION_IDS[-1] == MIGRATION_ID
    assert path.is_file()
    assert "CREATE TABLE IF NOT EXISTS rag_pipeline_versions" in content
    assert "CREATE TABLE IF NOT EXISTS rag_retrieval_traces" in content
    assert "CREATE TABLE IF NOT EXISTS rag_evaluation_runs" in content
    assert "CREATE TABLE IF NOT EXISTS rag_evaluation_results" in content
    assert "case_id BIGINT UNSIGNED NOT NULL" in content
    assert "ADD COLUMN IF NOT EXISTS answer_status" in content
    assert "ADD COLUMN IF NOT EXISTS expected_evidence_json" in content
    for forbidden in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM", "RENAME"):
        assert forbidden not in content


def test_init_sql_is_synced_with_enterprise_rag_migration():
    content = INIT_SQL.read_text(encoding="utf-8")

    for table in (
        "rag_pipeline_versions",
        "rag_retrieval_traces",
        "rag_evaluation_runs",
        "rag_evaluation_results",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in content
    for column in (
        "answer_status VARCHAR(32) NULL",
        "citation_manifest_json JSON NULL",
        "rag_trace_id INT NULL",
        "pipeline_version_key VARCHAR(64) NULL",
        "expected_evidence_json JSON NULL",
        "expected_status VARCHAR(32) NULL",
        "difficulty VARCHAR(32) NULL",
        "is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP",
        "case_id BIGINT UNSIGNED NOT NULL",
    ):
        assert column in content


def test_orm_models_match_new_rag_tables_and_additive_columns():
    assert RagPipelineVersion.__tablename__ == "rag_pipeline_versions"
    assert RagRetrievalTrace.__tablename__ == "rag_retrieval_traces"
    assert RagEvaluationRun.__tablename__ == "rag_evaluation_runs"
    assert RagEvaluationResult.__tablename__ == "rag_evaluation_results"

    qa_columns = QARecord.__table__.columns
    assert qa_columns["answer_status"].nullable is True
    assert qa_columns["citation_manifest_json"].nullable is True
    assert qa_columns["rag_trace_id"].nullable is True
    assert qa_columns["pipeline_version_key"].nullable is True

    eval_columns = RagEvalCase.__table__.columns
    assert eval_columns["expected_evidence_json"].nullable is True
    assert eval_columns["expected_status"].nullable is True
    assert eval_columns["difficulty"].nullable is True
    assert eval_columns["is_active"].nullable is False
    mysql_dialect = mysql.dialect()
    assert eval_columns["id"].type.compile(dialect=mysql_dialect) == "BIGINT UNSIGNED"
    assert (
        RagEvaluationResult.__table__.columns["case_id"].type.compile(
            dialect=mysql_dialect
        )
        == "BIGINT UNSIGNED"
    )


def test_legacy_qa_record_serializes_when_rag_core_fields_are_null():
    record = QARecord(
        user_id=1,
        question="旧问题",
        answer="旧回答",
        sources=[{"title": "旧来源"}],
    )

    payload = record.to_dict()

    assert payload["answer"] == "旧回答"
    assert payload["sources"] == [{"title": "旧来源"}]
    assert payload["answer_status"] is None
    assert payload["citations"] is None
    assert payload["rag_trace_id"] is None
    assert payload["pipeline_version"] is None

class _FakeScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar(self):
        return self._value


class _FakeMigrationConnection:
    def __init__(self):
        self.applied_migrations = set()
        self.executed_statements = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed_statements.append(sql)
        if "SELECT 1 FROM schema_migrations" in sql:
            migration_id = params["migration_id"]
            return _FakeScalarResult(
                1 if migration_id in self.applied_migrations else None
            )
        if "INSERT INTO schema_migrations" in sql:
            self.applied_migrations.add(params["migration_id"])
        return _FakeScalarResult()

    def exec_driver_sql(self, statement):
        self.executed_statements.append(statement)


class _FakeMigrationSession:
    def __init__(self, connection):
        self._connection = connection
        self.commit_count = 0
        self.rollback_count = 0

    def connection(self):
        return self._connection

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_migration_runner_applies_empty_registry_once_and_skips_repeat(monkeypatch):
    from app.scripts import apply_sql_migration as migration_module

    connection = _FakeMigrationConnection()
    session = _FakeMigrationSession(connection)
    monkeypatch.setattr(
        migration_module,
        "db",
        SimpleNamespace(session=session),
    )

    assert migration_module.apply_security_scanning_migration() is True
    assert MIGRATION_ID in connection.applied_migrations
    assert any(
        "CREATE TABLE IF NOT EXISTS rag_pipeline_versions" in statement
        for statement in connection.executed_statements
    )

    assert migration_module.apply_security_scanning_migration() is False
    assert session.rollback_count == 0
    assert session.commit_count == 2

class _DuplicateColumnDriverError(Exception):
    pass


class _DuplicateColumnConnection(_FakeMigrationConnection):
    def exec_driver_sql(self, statement):
        self.executed_statements.append(statement)
        if "answer_status" in statement:
            raise ProgrammingError(
                statement,
                {},
                _DuplicateColumnDriverError(1060, "duplicate column"),
            )


def test_migration_runner_uses_portable_add_column_and_only_ignores_duplicate(monkeypatch):
    from app.scripts import apply_sql_migration as migration_module

    connection = _DuplicateColumnConnection()
    session = _FakeMigrationSession(connection)
    monkeypatch.setattr(migration_module, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(migration_module, "MIGRATION_IDS", (MIGRATION_ID,))

    assert migration_module.apply_security_scanning_migration() is True
    assert MIGRATION_ID in connection.applied_migrations
    executed_add_column = next(
        statement
        for statement in connection.executed_statements
        if "answer_status" in statement
    )
    assert "ADD COLUMN IF NOT EXISTS" not in executed_add_column
