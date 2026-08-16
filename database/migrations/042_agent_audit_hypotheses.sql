-- 042：Harness V3 审计技能假设与 Evidence Critic 判定（additive only）。
-- 仅持久化受控技能、证据条件、位置元数据、状态与摘要；禁止存储源码、Prompt、
-- Provider 原始 reasoning、Token、Cookie 或其他凭据。

CREATE TABLE IF NOT EXISTS agent_audit_hypotheses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    hypothesis_key VARCHAR(64) NOT NULL,
    skill_key VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    target_summary VARCHAR(1000) NOT NULL,
    priority INT NOT NULL,
    status ENUM(
        'queued',
        'active',
        'needs_evidence',
        'confirmed',
        'rejected',
        'stopped_for_budget'
    ) NOT NULL DEFAULT 'queued',
    planner_source VARCHAR(64) NOT NULL,
    required_evidence_json JSON NOT NULL,
    authorized_scopes_json JSON NOT NULL,
    satisfied_evidence_json JSON NULL,
    evidence_gaps_json JSON NULL,
    reflection_count INT NOT NULL DEFAULT 0,
    execution_attempt_count INT NOT NULL DEFAULT 0,
    related_item_public_id VARCHAR(64) NULL,
    related_tool_call_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_audit_hypotheses_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    CONSTRAINT uq_agent_audit_hypotheses_run_key UNIQUE (run_id, hypothesis_key),
    INDEX ix_agent_audit_hypotheses_run_status (run_id, status),
    INDEX ix_agent_audit_hypotheses_run_priority (run_id, priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Harness V3 受控漏洞假设';

CREATE TABLE IF NOT EXISTS agent_audit_hypothesis_verdicts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hypothesis_id INT NOT NULL,
    verdict_version INT NOT NULL,
    verdict ENUM(
        'confirm_candidate',
        'request_evidence',
        'reject_hypothesis',
        'needs_more_evidence',
        'stop_for_budget'
    ) NOT NULL,
    reason_summary VARCHAR(2000) NOT NULL,
    evidence_gaps_json JSON NULL,
    next_action_json JSON NULL,
    critic_version VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_audit_hypothesis_verdicts_hypothesis
        FOREIGN KEY (hypothesis_id) REFERENCES agent_audit_hypotheses(id) ON DELETE CASCADE,
    CONSTRAINT uq_agent_audit_hypothesis_verdict_version UNIQUE (hypothesis_id, verdict_version),
    INDEX ix_agent_audit_hypothesis_verdicts_hypothesis (hypothesis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Harness V3 Evidence Critic 结构化判定';