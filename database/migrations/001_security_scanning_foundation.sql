-- CyberGuard security scanning foundation (additive migration)
-- Apply to an existing MySQL 8+ CyberGuard database. This migration does not alter or delete legacy tables.

CREATE TABLE IF NOT EXISTS workspaces (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspaces_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全工作区';

CREATE TABLE IF NOT EXISTS workspace_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    user_id INT NOT NULL,
    role ENUM('owner', 'security_admin', 'analyst', 'developer', 'viewer') NOT NULL DEFAULT 'viewer',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspace_membership UNIQUE (workspace_id, user_id),
    CONSTRAINT fk_workspace_members_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_workspace_members_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_workspace_members_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作区成员';

CREATE TABLE IF NOT EXISTS security_projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT NULL,
    default_branch VARCHAR(255) NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspace_project_name UNIQUE (workspace_id, name),
    CONSTRAINT fk_security_projects_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_security_projects_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_security_projects_workspace_id (workspace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全扫描项目';

CREATE TABLE IF NOT EXISTS project_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    source_type ENUM('zip', 'github') NOT NULL,
    source_ref VARCHAR(2048) NULL,
    commit_sha VARCHAR(128) NULL,
    content_sha256 CHAR(64) NOT NULL,
    storage_path VARCHAR(1024) NULL,
    file_count INT NOT NULL DEFAULT 0,
    total_bytes BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_project_snapshot_content UNIQUE (project_id, content_sha256),
    CONSTRAINT fk_project_snapshots_project FOREIGN KEY (project_id) REFERENCES security_projects(id) ON DELETE CASCADE,
    INDEX ix_project_snapshots_project_id (project_id),
    INDEX ix_project_snapshots_commit_sha (commit_sha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='不可变项目快照';

CREATE TABLE IF NOT EXISTS scan_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    status ENUM('created', 'validating', 'snapshotting', 'scanning', 'completed', 'completed_with_warnings', 'failed', 'canceled') NOT NULL DEFAULT 'created',
    progress INT NOT NULL DEFAULT 0,
    policy_version VARCHAR(100) NULL,
    worker_id VARCHAR(255) NULL,
    error_code VARCHAR(100) NULL,
    error_message TEXT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    canceled_at DATETIME NULL,
    summary_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_scan_tasks_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE,
    INDEX ix_scan_tasks_snapshot_id (snapshot_id),
    INDEX ix_scan_tasks_status (status),
    INDEX ix_scan_tasks_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='异步扫描任务';

CREATE TABLE IF NOT EXISTS security_findings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    fingerprint VARCHAR(128) NOT NULL,
    rule_id VARCHAR(128) NOT NULL,
    category ENUM('sast', 'secret', 'sca', 'configuration') NOT NULL,
    severity ENUM('critical', 'high', 'medium', 'low', 'info') NOT NULL,
    status ENUM('open', 'triaged', 'accepted_risk', 'false_positive', 'resolved') NOT NULL DEFAULT 'open',
    cwe_id VARCHAR(32) NULL,
    cve_id VARCHAR(32) NULL,
    file_path VARCHAR(1024) NOT NULL,
    start_line INT NOT NULL,
    end_line INT NULL,
    message TEXT NOT NULL,
    confidence FLOAT NULL,
    rule_version VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_task_finding_fingerprint UNIQUE (task_id, fingerprint),
    CONSTRAINT fk_security_findings_task FOREIGN KEY (task_id) REFERENCES scan_tasks(id) ON DELETE CASCADE,
    INDEX ix_security_findings_task_id (task_id),
    INDEX ix_security_findings_severity (severity),
    INDEX ix_security_findings_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准化安全发现项';

CREATE TABLE IF NOT EXISTS finding_evidences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    finding_id INT NOT NULL,
    evidence_type ENUM('code', 'secret', 'dependency', 'configuration', 'rag_reference') NOT NULL,
    content_redacted TEXT NOT NULL,
    secret_hash VARCHAR(128) NULL,
    source_uri VARCHAR(2048) NULL,
    start_line INT NULL,
    end_line INT NULL,
    score FLOAT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_finding_evidences_finding FOREIGN KEY (finding_id) REFERENCES security_findings(id) ON DELETE CASCADE,
    INDEX ix_finding_evidences_finding_id (finding_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='脱敏漏洞证据';

CREATE TABLE IF NOT EXISTS audit_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    actor_id INT NULL,
    action VARCHAR(128) NOT NULL,
    target_type VARCHAR(128) NOT NULL,
    target_id INT NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_events_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_events_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_audit_events_workspace_created (workspace_id, created_at),
    INDEX ix_audit_events_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全域审计事件';
