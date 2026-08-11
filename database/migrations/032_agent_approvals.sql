-- A7 危险操作审批与人工审核：agent_approvals（additive only）
-- 迁移 032：审批请求绑定 operation_digest 防重放，单次使用，可过期；
-- 决策写 Durable Event 与 AuditEvent，拒绝后不自动放行。

CREATE TABLE IF NOT EXISTS agent_approvals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    workspace_id INT NOT NULL,
    operation_type VARCHAR(64) NOT NULL,
    risk_level VARCHAR(16) NOT NULL DEFAULT 'medium',
    reason VARCHAR(1000) NOT NULL,
    affected_scope_json JSON NULL,
    operation_digest VARCHAR(64) NOT NULL,
    proposed_json JSON NULL COMMENT '批准后生效的配置（如新预算上限）',
    requested_by INT NULL,
    status ENUM('pending', 'approved', 'rejected', 'expired', 'canceled') NOT NULL DEFAULT 'pending',
    decision_comment VARCHAR(1000) NULL,
    resolver_id INT NULL,
    expires_at DATETIME NULL,
    resolved_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_agent_approvals_digest (operation_digest),
    CONSTRAINT fk_agent_approvals_run
        FOREIGN KEY (run_id) REFERENCES agent_runs (id) ON DELETE CASCADE,
    INDEX ix_agent_approvals_run (run_id),
    INDEX ix_agent_approvals_workspace (workspace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='A7 危险操作审批请求';
