-- CyberGuard Phase 4 task reliability additions (additive only).
-- Existing rows remain valid: dispatch_key is nullable for historical tasks.

ALTER TABLE scan_tasks
    ADD COLUMN dispatch_key VARCHAR(64) NULL AFTER worker_id,
    ADD COLUMN retry_count INT NOT NULL DEFAULT 0 AFTER dispatch_key,
    ADD CONSTRAINT uq_scan_tasks_dispatch_key UNIQUE (dispatch_key),
    ADD INDEX ix_scan_tasks_dispatch_key (dispatch_key);