from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app import db
from app.config import Config
from app.models.security import (
    ProjectSnapshot,
    RemediationSuggestion,
    ScanTask,
    SecurityFinding,
    SecurityKnowledgeDocument,
    SecurityKnowledgeSource,
    SecurityProject,
    Workspace,
)
from app.models.user import User
from app.scripts.apply_sql_migration import MIGRATION_IDS, _statements


def make_workspace_finding() -> tuple[Workspace, User, SecurityFinding]:
    user = User(username="remediation-owner", email="remediation-owner@example.test", password_hash="x")
    workspace = Workspace(name="Remediation Workspace", slug="remediation-workspace")
    db.session.add_all([user, workspace])
    db.session.flush()

    project = SecurityProject(workspace_id=workspace.id, name="demo", created_by=user.id)
    db.session.add(project)
    db.session.flush()

    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="b" * 64,
        file_count=1,
        total_bytes=1,
    )
    db.session.add(snapshot)
    db.session.flush()

    task = ScanTask(snapshot_id=snapshot.id, status="completed", progress=100)
    db.session.add(task)
    db.session.flush()

    finding = SecurityFinding(
        task_id=task.id,
        fingerprint="finding-for-remediation",
        rule_id="PY-SHELL-TRUE",
        category="sast",
        severity="high",
        file_path="app.py",
        start_line=10,
        message="Avoid shell=True with untrusted input",
    )
    db.session.add(finding)
    db.session.flush()
    return workspace, user, finding


def test_knowledge_sources_and_documents_are_workspace_scoped_and_safe_to_serialize(app):
    with app.app_context():
        workspace, _, _ = make_workspace_finding()
        source = SecurityKnowledgeSource(
            workspace_id=workspace.id,
            name="OWASP guidance",
            source_type="standard",
            source_uri="https://owasp.org/example",
            license_name="CC BY-SA 4.0",
            source_version="2026.1",
            content_hash="a" * 64,
            metadata_json={"internal_note": "do not expose"},
        )
        document = SecurityKnowledgeDocument(
            source=source,
            document_version="2026.1-section-1",
            title="Command injection prevention",
            content="Use parameterized process invocation.",
            summary="Prefer argument vectors over shell parsing.",
            tags_json=["owasp", "command-injection"],
            framework_metadata_json={"controls": ["ASVS-5.3.8"]},
            effective_from=datetime.utcnow() - timedelta(days=1),
        )
        db.session.add(source)
        db.session.commit()

        assert source.workspace is workspace
        assert workspace.knowledge_sources == [source]
        assert document.source is source
        assert source.documents == [document]
        assert document.workspace_id == workspace.id

        source_data = source.to_dict()
        document_data = document.to_dict()
        document_with_content = document.to_dict(include_content=True)

        assert source_data["workspace_id"] == workspace.id
        assert source_data["source_version"] == "2026.1"
        assert "metadata" not in source_data
        assert "content" not in source_data
        assert document_data["source_id"] == source.id
        assert document_data["tags"] == ["owasp", "command-injection"]
        assert "content" not in document_data
        assert "framework_metadata" not in document_data
        assert document_with_content["content"] == "Use parameterized process invocation."


def test_knowledge_document_version_is_unique_within_a_source(app):
    with app.app_context():
        workspace, _, _ = make_workspace_finding()
        source = SecurityKnowledgeSource(
            workspace_id=workspace.id,
            name="NIST guidance",
            source_type="standard",
            source_version="1",
        )
        db.session.add(source)
        db.session.flush()
        db.session.add(
            SecurityKnowledgeDocument(
                source_id=source.id,
                document_version="v1",
                title="First",
                content="first version",
            )
        )
        db.session.commit()

        db.session.add(
            SecurityKnowledgeDocument(
                source_id=source.id,
                document_version="v1",
                title="Duplicate",
                content="duplicate version",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_remediation_suggestion_has_review_constraints_and_safe_serialization(app):
    with app.app_context():
        _, reviewer, finding = make_workspace_finding()
        suggestion = RemediationSuggestion(
            finding_id=finding.id,
            rationale="The finding indicates shell parsing of untrusted input.",
            remediation_steps_json=["Use subprocess.run with an argument list."],
            patch_diff="--- a/app.py\n+++ b/app.py\n",
            citations_json=[{"document_id": 1, "citation_id": "knowledge-1"}],
            warning_codes_json=["PATCH_NOT_VALIDATED"],
            provider="rule_based",
            model="deterministic-advisor",
            model_version="1",
            confidence=0.8,
        )
        db.session.add(suggestion)
        db.session.commit()

        assert finding.remediation_suggestions == [suggestion]
        assert suggestion.review_state == "pending"

        suggestion.review_state = "accepted"
        suggestion.reviewer_id = reviewer.id
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.review_comment = "Reviewed against the finding evidence."
        db.session.commit()

        serialized = suggestion.to_dict()
        assert serialized["review_state"] == "accepted"
        assert serialized["citations"] == [{"document_id": 1, "citation_id": "knowledge-1"}]
        assert serialized["warning_codes"] == ["PATCH_NOT_VALIDATED"]
        assert "raw_prompt" not in serialized
        assert "raw_model_response" not in serialized
        assert "raw_prompt" not in suggestion.__table__.columns
        assert "raw_model_response" not in suggestion.__table__.columns

        suggestion.review_state = "auto_applied"
        with pytest.raises((IntegrityError, StatementError)):
            db.session.commit()
        db.session.rollback()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("REMEDIATION_MAX_CONTEXT_CHARS", 0, "REMEDIATION_MAX_CONTEXT_CHARS"),
        ("REMEDIATION_MAX_OUTPUT_CHARS", "not-a-number", "REMEDIATION_MAX_OUTPUT_CHARS"),
        ("REMEDIATION_RETRIEVAL_TOP_K", 51, "REMEDIATION_RETRIEVAL_TOP_K"),
        ("REMEDIATION_PATCH_MAX_LINES", 5001, "REMEDIATION_PATCH_MAX_LINES"),
        ("REMEDIATION_PATCH_MAX_CHARS", 500_001, "REMEDIATION_PATCH_MAX_CHARS"),
        ("REMEDIATION_LLM_ENABLED", "sometimes", "REMEDIATION_LLM_ENABLED"),
    ],
)
def test_remediation_config_validation_rejects_invalid_mapping_values(field, value, message):
    settings = {
        "APP_ENV": "testing",
        "CORS_ALLOWED_ORIGINS": ["https://security.example.test"],
        "SECURITY_WORKSPACE_ROOT": "security-workspaces",
        "REDIS_URL": "redis://localhost:6379/0",
        "RQ_QUEUE_NAME": "cyberguard-security-test",
        "RQ_ASYNC": False,
        "ARCHIVE_MAX_UPLOAD_BYTES": 50 * 1024 * 1024,
        "ARCHIVE_MAX_EXTRACT_BYTES": 500 * 1024 * 1024,
        "ARCHIVE_MAX_FILES": 20_000,
        "ARCHIVE_MAX_DEPTH": 10,
        "GITHUB_API_TIMEOUT_SECONDS": 15,
        "GITHUB_MAX_REDIRECTS": 1,
        "SCA_OSV_API_URL": "https://api.osv.dev/v1/querybatch",
        "SCA_REQUEST_TIMEOUT_SECONDS": 15,
        "SCA_CACHE_TTL_SECONDS": 86_400,
        "SCA_MAX_DEPENDENCIES": 10_000,
        "SECURITY_KNOWLEDGE_VECTOR_ENABLED": "false",
        "REMEDIATION_LLM_ENABLED": "false",
        "REMEDIATION_MAX_CONTEXT_CHARS": 12_000,
        "REMEDIATION_MAX_OUTPUT_CHARS": 8_000,
        "REMEDIATION_RETRIEVAL_TOP_K": 5,
        "REMEDIATION_PATCH_MAX_LINES": 500,
        "REMEDIATION_PATCH_MAX_CHARS": 50_000,
    }
    settings[field] = value

    with pytest.raises(ValueError, match=message):
        Config.validate_security_settings(settings)


def test_remediation_config_validation_accepts_string_mapping_values():
    settings = {
        "APP_ENV": "testing",
        "CORS_ALLOWED_ORIGINS": "https://security.example.test",
        "SECURITY_WORKSPACE_ROOT": "security-workspaces",
        "REDIS_URL": "redis://localhost:6379/0",
        "RQ_QUEUE_NAME": "cyberguard-security-test",
        "RQ_ASYNC": "false",
        "ARCHIVE_MAX_UPLOAD_BYTES": "52428800",
        "ARCHIVE_MAX_EXTRACT_BYTES": "524288000",
        "ARCHIVE_MAX_FILES": "20000",
        "ARCHIVE_MAX_DEPTH": "10",
        "GITHUB_API_TIMEOUT_SECONDS": "15",
        "GITHUB_MAX_REDIRECTS": "1",
        "SCA_OSV_API_URL": "https://api.osv.dev/v1/querybatch",
        "SCA_REQUEST_TIMEOUT_SECONDS": "15",
        "SCA_CACHE_TTL_SECONDS": "86400",
        "SCA_MAX_DEPENDENCIES": "10000",
        "SECURITY_KNOWLEDGE_VECTOR_ENABLED": "true",
        "REMEDIATION_LLM_ENABLED": "false",
        "REMEDIATION_MAX_CONTEXT_CHARS": "12000",
        "REMEDIATION_MAX_OUTPUT_CHARS": "8000",
        "REMEDIATION_RETRIEVAL_TOP_K": "5",
        "REMEDIATION_PATCH_MAX_LINES": "500",
        "REMEDIATION_PATCH_MAX_CHARS": "50000",
    }

    Config.validate_security_settings(settings)


def test_phase_three_schema_is_in_init_sql_and_ordered_migration_runner():
    repository_root = Path(__file__).resolve().parents[2]
    migration_sql = (
        repository_root / "database" / "migrations" / "003_trusted_agent_rag_remediation.sql"
    ).read_text(encoding="utf-8")
    init_sql = (repository_root / "database" / "init.sql").read_text(encoding="utf-8")

    assert MIGRATION_IDS == (
        "001_security_scanning_foundation",
        "002_github_multilang_sca",
        "003_trusted_agent_rag_remediation",
        "004_phase4_task_reliability",
        "005_legal_policies",
        "006_oauth_login",
        "007_multi_oauth_bindings",
        "008_qa_rag_warnings",
        "009_user_preferences",
        "010_scan_exclusion_rules",
        "011_agent_runtime_events",
        "012_scan_coverage_receipts",
        "013_agent_conversations",
        "014_llm_operations",
        "015_llm_cache_telemetry",
        "016_user_memories",
        "017_agent_llm_invocations_cost",
        "018_qa_retrieval_eval",
        "019_user_font_size",
        "020_memory_eval_cases",
        "021_help_center",
        "022_llm_provider_max_tokens",
        "023_user_qa_max_tokens",
        "024_memory_governance",
        "025_memory_entities_dream",
        "026_qa_record_reasoning",
        "027_project_security_graph",
        "028_knowledge_content_mediumtext",
        "029_kg_community_summaries",
        "030_agent_replan_decisions",
        "031_agent_observations",
    )
    assert len(_statements(migration_sql)) == 3
    for table_name in (
        "security_knowledge_sources",
        "security_knowledge_documents",
        "remediation_suggestions",
    ):
        assert table_name in migration_sql
        assert table_name in init_sql

    assert "raw_prompt" not in migration_sql
    assert "dispatch_key VARCHAR(64) NULL" in init_sql
    assert "retry_count INT NOT NULL DEFAULT 0" in init_sql
    assert "raw_model_response" not in migration_sql


def test_phase_four_migration_is_additive_and_registered():
    repository_root = Path(__file__).resolve().parents[2]
    migration_path = repository_root / "database" / "migrations" / "004_phase4_task_reliability.sql"
    migration_sql = migration_path.read_text(encoding="utf-8")

    assert "004_phase4_task_reliability" in MIGRATION_IDS
    assert migration_path.exists()
    assert "ALTER TABLE scan_tasks" in migration_sql
    assert "dispatch_key" in migration_sql
    assert "retry_count" in migration_sql
    assert "DROP " not in migration_sql.upper()
    assert "TRUNCATE" not in migration_sql.upper()
    assert "DELETE FROM" not in migration_sql.upper()
