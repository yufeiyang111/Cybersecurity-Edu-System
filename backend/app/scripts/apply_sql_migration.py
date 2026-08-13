"""Idempotent runner for ordered additive security-schema migrations."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app import db

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[3] / "database" / "migrations"
MIGRATION_IDS = (
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
    "032_agent_approvals",
    "033_workspace_provider_policy",
    "034_analytics_preferences",
    "035_agent_loop_items",
    "036_workspace_agent_feature_flags",
)


def _statements(sql: str) -> list[str]:
    """Split this repository's plain DDL migrations into executable statements."""
    lines = [line for line in sql.splitlines() if not line.lstrip().startswith("--")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def _migration_file(migration_id: str) -> Path:
    return MIGRATIONS_DIRECTORY / f"{migration_id}.sql"


def apply_security_scanning_migration() -> bool:
    """Apply every known additive migration once, in stable identifier order."""
    migration_files = [(_migration_id, _migration_file(_migration_id)) for _migration_id in MIGRATION_IDS]
    missing_files = [path for _, path in migration_files if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"Migration file does not exist: {missing_files[0]}")

    connection = db.session.connection()
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id VARCHAR(128) NOT NULL PRIMARY KEY,
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

    applied_any = False
    try:
        for migration_id, migration_file in migration_files:
            already_applied = connection.execute(
                text("SELECT 1 FROM schema_migrations WHERE migration_id = :migration_id"),
                {"migration_id": migration_id},
            ).scalar()
            if already_applied:
                continue

            for statement in _statements(migration_file.read_text(encoding="utf-8")):
                connection.exec_driver_sql(statement)
            connection.execute(
                text("INSERT INTO schema_migrations (migration_id) VALUES (:migration_id)"),
                {"migration_id": migration_id},
            )
            applied_any = True
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return applied_any
