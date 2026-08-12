-- CyberGuard Agent Loop v2 foundation (additive only, T02).
-- Unified timeline items, ordered control inputs and conversation summaries;
-- plus additive columns on agent_events / agent_runs / agent_tool_calls /
-- agent_checkpoints. All statements are idempotent create-or-alter-add.

CREATE TABLE IF NOT EXISTS agent_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL,
    conversation_id INT NULL,
    turn_id INT NULL,
    run_id INT NOT NULL,
    iteration INT NOT NULL DEFAULT 0,
    item_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'started',
    parent_item_id VARCHAR(64) NULL,
    content_redacted MEDIUMTEXT NULL,
    summary_json JSON NULL,
    sensitive_level VARCHAR(32) NOT NULL DEFAULT 'internal',
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_agent_items_public_id UNIQUE (public_id),
    CONSTRAINT fk_agent_items_conversation FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id),
    CONSTRAINT fk_agent_items_turn FOREIGN KEY (turn_id) REFERENCES agent_turns(id),
    CONSTRAINT fk_agent_items_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    INDEX ix_agent_items_run_created (run_id, created_at),
    INDEX ix_agent_items_run_type (run_id, item_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Unified agent timeline items';

CREATE TABLE IF NOT EXISTS agent_control_inputs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL,
    conversation_id INT NULL,
    turn_id INT NULL,
    run_id INT NOT NULL,
    input_type VARCHAR(32) NOT NULL,
    client_request_id VARCHAR(64) NOT NULL,
    payload_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    applied_iteration INT NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_at DATETIME NULL,
    CONSTRAINT uq_agent_control_inputs_run_request UNIQUE (run_id, client_request_id),
    CONSTRAINT fk_agent_control_inputs_conversation FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id),
    CONSTRAINT fk_agent_control_inputs_turn FOREIGN KEY (turn_id) REFERENCES agent_turns(id),
    CONSTRAINT fk_agent_control_inputs_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_control_inputs_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_agent_control_inputs_run_status (run_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Ordered agent control inputs';

CREATE TABLE IF NOT EXISTS agent_conversation_summaries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    summary_version INT NOT NULL,
    source_sequence_from INT NOT NULL,
    source_sequence_to INT NOT NULL,
    summary_json JSON NOT NULL,
    content_digest VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_agent_conversation_summaries_version UNIQUE (conversation_id, summary_version),
    CONSTRAINT fk_agent_conversation_summaries_conv FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id) ON DELETE CASCADE,
    INDEX ix_agent_conversation_summaries_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Structured conversation compression summaries';

-- agent_events: v2 item envelope columns
ALTER TABLE agent_events ADD COLUMN conversation_id INT NULL;
ALTER TABLE agent_events ADD COLUMN turn_id INT NULL;
ALTER TABLE agent_events ADD COLUMN iteration INT NOT NULL DEFAULT 0;
ALTER TABLE agent_events ADD COLUMN item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_events ADD COLUMN parent_item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_events ADD COLUMN dedupe_key VARCHAR(255) NULL;

-- agent_runs: loop state columns
ALTER TABLE agent_runs ADD COLUMN iteration_count INT NOT NULL DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN max_iterations INT NULL;
ALTER TABLE agent_runs ADD COLUMN current_item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_runs ADD COLUMN policy_snapshot_json JSON NULL;
ALTER TABLE agent_runs ADD COLUMN tool_catalog_digest VARCHAR(64) NULL;
ALTER TABLE agent_runs ADD COLUMN context_watermark INT NOT NULL DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN last_checkpoint_id INT NULL;

-- agent_tool_calls: provider/tool governance columns
ALTER TABLE agent_tool_calls ADD COLUMN provider_call_id VARCHAR(128) NULL;
ALTER TABLE agent_tool_calls ADD COLUMN logical_call_key VARCHAR(255) NULL;
ALTER TABLE agent_tool_calls ADD COLUMN attempt_number INT NOT NULL DEFAULT 1;
ALTER TABLE agent_tool_calls ADD COLUMN arguments_digest VARCHAR(64) NULL;
ALTER TABLE agent_tool_calls ADD COLUMN result_schema_version INT NULL;
ALTER TABLE agent_tool_calls ADD COLUMN retryable TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE agent_tool_calls ADD COLUMN deadline_at DATETIME NULL;
ALTER TABLE agent_tool_calls ADD COLUMN item_public_id VARCHAR(64) NULL;

-- agent_checkpoints: recovery watermark columns
ALTER TABLE agent_checkpoints ADD COLUMN iteration INT NOT NULL DEFAULT 0;
ALTER TABLE agent_checkpoints ADD COLUMN context_watermark INT NOT NULL DEFAULT 0;
ALTER TABLE agent_checkpoints ADD COLUMN current_item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_checkpoints ADD COLUMN lease_owner VARCHAR(255) NULL;
ALTER TABLE agent_checkpoints ADD COLUMN checkpoint_digest VARCHAR(64) NULL;
