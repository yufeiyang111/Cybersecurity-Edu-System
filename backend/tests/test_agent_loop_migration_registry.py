# -*- coding: utf-8 -*-
"""T02 迁移注册测试：编号唯一、顺序稳定、文件存在、init.sql 同构、无破坏性 SQL。"""
from __future__ import annotations

from pathlib import Path

from app.scripts.apply_sql_migration import MIGRATION_IDS

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BACKEND_ROOT / "database" / "migrations"
INIT_SQL = BACKEND_ROOT / "database" / "init.sql"

AGENT_LOOP_MIGRATION = "035_agent_loop_items"
AGENT_FLAGS_MIGRATION = "036_workspace_agent_feature_flags"
AGENT_SSE_HEALTH_MIGRATION = "037_agent_sse_health"
ENTERPRISE_RAG_CORE_MIGRATION = "038_enterprise_rag_core"


def test_migration_ids_unique_and_ordered():
    assert len(MIGRATION_IDS) == len(set(MIGRATION_IDS))
    assert MIGRATION_IDS == tuple(sorted(MIGRATION_IDS))


def test_agent_loop_migration_precedes_all_later_migrations_in_order():
    assert AGENT_LOOP_MIGRATION in MIGRATION_IDS
    index = MIGRATION_IDS.index(AGENT_LOOP_MIGRATION)
    assert MIGRATION_IDS[index - 1] == "034_analytics_preferences"
    assert MIGRATION_IDS[index + 1:] == (
        "036_workspace_agent_feature_flags",
        "037_agent_sse_health",
        "038_enterprise_rag_core",
    )


def test_agent_flags_migration_precedes_sse_and_enterprise_rag_core():
    assert AGENT_FLAGS_MIGRATION in MIGRATION_IDS
    assert AGENT_SSE_HEALTH_MIGRATION in MIGRATION_IDS
    assert ENTERPRISE_RAG_CORE_MIGRATION in MIGRATION_IDS
    flags_index = MIGRATION_IDS.index(AGENT_FLAGS_MIGRATION)
    sse_index = MIGRATION_IDS.index(AGENT_SSE_HEALTH_MIGRATION)
    rag_core_index = MIGRATION_IDS.index(ENTERPRISE_RAG_CORE_MIGRATION)
    assert flags_index == sse_index - 1
    assert sse_index == rag_core_index - 1
    assert rag_core_index == len(MIGRATION_IDS) - 1



def test_agent_flags_migration_file_and_init_sql_synced():
    path = MIGRATIONS_DIR / f"{AGENT_FLAGS_MIGRATION}.sql"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "ADD COLUMN agent_feature_flags" in content
    init_sql = INIT_SQL.read_text(encoding="utf-8")
    assert "agent_feature_flags JSON NULL" in init_sql


def test_migration_file_exists_with_new_tables():
    path = MIGRATIONS_DIR / f"{AGENT_LOOP_MIGRATION}.sql"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert content.strip()
    assert "CREATE TABLE IF NOT EXISTS agent_items" in content
    assert "CREATE TABLE IF NOT EXISTS agent_control_inputs" in content
    assert "CREATE TABLE IF NOT EXISTS agent_conversation_summaries" in content


def test_migration_has_no_destructive_statements():
    path = MIGRATIONS_DIR / f"{AGENT_LOOP_MIGRATION}.sql"
    content = path.read_text(encoding="utf-8")
    for token in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM", "RENAME"):
        assert token not in content


def test_init_sql_contains_new_tables():
    content = INIT_SQL.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS agent_items" in content
    assert "CREATE TABLE IF NOT EXISTS agent_control_inputs" in content
    assert "CREATE TABLE IF NOT EXISTS agent_conversation_summaries" in content


def test_init_sql_contains_extended_columns():
    content = INIT_SQL.read_text(encoding="utf-8")
    assert "item_public_id" in content
    assert "dedupe_key" in content
    assert "policy_snapshot_json" in content
    assert "logical_call_key" in content
    assert "checkpoint_digest" in content
