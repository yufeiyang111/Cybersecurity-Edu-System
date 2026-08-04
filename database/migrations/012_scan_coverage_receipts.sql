-- CyberGuard scan coverage foundation (additive only).
-- Immutable per-snapshot file catalog plus idempotent per-scan receipts so the
-- agent and the UI can answer "what was scanned" instead of only seeing files
-- that produced findings.

CREATE TABLE IF NOT EXISTS project_snapshot_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    extension VARCHAR(64) NULL,
    is_text TINYINT(1) NOT NULL DEFAULT 0,
    detected_language VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_snapshot_files_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE,
    CONSTRAINT uq_snapshot_files_path UNIQUE (snapshot_id, file_path),
    INDEX ix_snapshot_files_snapshot_text (snapshot_id, is_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Immutable snapshot file catalog';

CREATE TABLE IF NOT EXISTS scan_file_receipts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    snapshot_id INT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    scanner_name VARCHAR(128) NOT NULL,
    coverage_kind ENUM('accounted', 'baseline_scanned', 'specialized_sast', 'generic_only', 'scanned_no_finding', 'scanned_with_findings', 'excluded', 'skipped', 'failed') NOT NULL DEFAULT 'accounted',
    file_size BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scan_receipts_task FOREIGN KEY (task_id) REFERENCES scan_tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_scan_receipts_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE,
    CONSTRAINT uq_scan_receipts_scope UNIQUE (task_id, file_path, scanner_name, coverage_kind),
    INDEX ix_scan_receipts_task_status (task_id, coverage_kind),
    INDEX ix_scan_receipts_snapshot (snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Idempotent per-file scan receipts';
