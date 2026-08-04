-- CyberGuard project-level scan exclusion rules (additive only).
-- Gitignore-style rules hide privacy-sensitive files from snapshots and scanning.

CREATE TABLE IF NOT EXISTS project_exclusion_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    pattern VARCHAR(500) NOT NULL,
    position INT NOT NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_exclusion_rules_project FOREIGN KEY (project_id) REFERENCES security_projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_exclusion_rules_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_exclusion_rules_position UNIQUE (project_id, position),
    INDEX ix_exclusion_rules_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目级扫描排除规则';

ALTER TABLE scan_tasks
    ADD COLUMN exclusion_rules JSON NULL AFTER policy_version;
