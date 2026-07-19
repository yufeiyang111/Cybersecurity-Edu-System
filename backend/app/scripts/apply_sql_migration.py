"""Small idempotent runner for the first additive security-schema migration."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app import db

MIGRATION_ID = "001_security_scanning_foundation"
MIGRATION_FILE = Path(__file__).resolve().parents[3] / "database" / "migrations" / f"{MIGRATION_ID}.sql"


def _statements(sql: str) -> list[str]:
    """Split this repository's plain DDL migration into executable statements."""
    lines = [line for line in sql.splitlines() if not line.lstrip().startswith("--")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def apply_security_scanning_migration() -> bool:
    """Apply the additive migration once and persist its migration identifier."""
    if not MIGRATION_FILE.is_file():
        raise FileNotFoundError(f"Migration file does not exist: {MIGRATION_FILE}")

    connection = db.session.connection()
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id VARCHAR(128) NOT NULL PRIMARY KEY,
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    already_applied = connection.execute(
        text("SELECT 1 FROM schema_migrations WHERE migration_id = :migration_id"),
        {"migration_id": MIGRATION_ID},
    ).scalar()
    if already_applied:
        return False

    for statement in _statements(MIGRATION_FILE.read_text(encoding="utf-8")):
        connection.exec_driver_sql(statement)
    connection.execute(
        text("INSERT INTO schema_migrations (migration_id) VALUES (:migration_id)"),
        {"migration_id": MIGRATION_ID},
    )
    db.session.commit()
    return True
