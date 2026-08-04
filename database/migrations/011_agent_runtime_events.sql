-- CyberGuard agent runtime foundation (additive only).
-- Durable AgentRun, plan DAG, step/tool executions, artifacts, checkpoints
-- and replayable AgentEvent stream.  Agent tables do NOT cascade from projects
-- so the audit trail survives project-level cleanup decisions.

CREATE TABLE IF NOT EXISTS agent_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    project_id INT NOT NULL,
    snapshot_id INT NOT NULL,
    created_by INT NULL,
    goal_text VARCHAR(4000) NOT NULL,
    mode ENUM('baseline', 'hybrid', 'deep_audit') NOT NULL DEFAULT 'baseline',
    status ENUM('created', 'queued', 'preparing', 'mapping_repository', 'planning', 'validating_plan', 'executing_tools', 'evaluating_evidence', 'replanning', 'deep_reviewing', 'awaiting_approval', 'paused', 'generating_report', 'completed', 'completed_with_warnings', 'partial', 'failed', 'canceled') NOT NULL DEFAULT 'created',
    state_version INT NOT NULL DEFAULT 0,
    plan_version INT NOT NULL DEFAULT 0,
    planner_source VARCHAR(64) NULL,
    last_event_sequence INT NOT NULL DEFAULT 0,
    lease_owner VARCHAR(255) NULL,
    lease_expires_at DATETIME NULL,
    heartbeat_at DATETIME NULL,
    tool_call_count INT NOT NULL DEFAULT 0,
    llm_call_count INT NOT NULL DEFAULT 0,
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cached_input_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    max_llm_calls INT NULL,
    max_tool_calls INT NULL,
    max_total_tokens INT NULL,
    max_estimated_cost DECIMAL(12, 6) NULL,
    max_wall_clock_seconds INT NULL,
    max_deep_review_files INT NULL,
    warning_codes JSON NULL,
    error_code VARCHAR(100) NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_runs_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_agent_runs_project FOREIGN KEY (project_id) REFERENCES security_projects(id),
    CONSTRAINT fk_agent_runs_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id),
    CONSTRAINT fk_agent_runs_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_agent_runs_workspace_created (workspace_id, created_at),
    INDEX ix_agent_runs_status_lease (status, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Durable agent runs';

CREATE TABLE IF NOT EXISTS agent_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    role VARCHAR(32) NOT NULL,
    content VARCHAR(8000) NOT NULL,
    message_type VARCHAR(64) NOT NULL DEFAULT 'user_goal',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_messages_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_messages_run_created (run_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent run user messages';

CREATE TABLE IF NOT EXISTS agent_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    planner_source VARCHAR(64) NOT NULL,
    objective VARCHAR(4000) NULL,
    decision_summary VARCHAR(4000) NULL,
    hypotheses_json JSON NULL,
    completion_criteria_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plans_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_plans_run_version UNIQUE (run_id, plan_version),
    INDEX ix_agent_plans_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned agent plans';

CREATE TABLE IF NOT EXISTS agent_plan_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id INT NOT NULL,
    node_key VARCHAR(64) NOT NULL,
    node_type ENUM('inventory', 'baseline_scan', 'coverage_analysis', 'repository_mapping', 'risk_ranking', 'rag_retrieval', 'semantic_review', 'human_approval', 'remediation_generation', 'report_generation') NOT NULL,
    status ENUM('pending', 'ready', 'running', 'succeeded', 'failed', 'skipped', 'blocked', 'canceled', 'superseded') NOT NULL DEFAULT 'pending',
    title VARCHAR(500) NOT NULL,
    description VARCHAR(4000) NULL,
    tool_name VARCHAR(128) NULL,
    depends_on_json JSON NULL,
    input_artifact_refs JSON NULL,
    output_artifact_refs JSON NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plan_nodes_plan FOREIGN KEY (plan_id) REFERENCES agent_plans(id),
    CONSTRAINT uq_agent_plan_nodes_key UNIQUE (plan_id, node_key),
    INDEX ix_agent_plan_nodes_plan_status (plan_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan DAG nodes';

CREATE TABLE IF NOT EXISTS agent_plan_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id INT NOT NULL,
    from_node VARCHAR(64) NOT NULL,
    to_node VARCHAR(64) NOT NULL,
    edge_type ENUM('success', 'failure', 'condition', 'always', 'evidence_gap', 'approval_granted', 'approval_rejected', 'budget_available') NOT NULL DEFAULT 'success',
    condition_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plan_edges_plan FOREIGN KEY (plan_id) REFERENCES agent_plans(id),
    INDEX ix_agent_plan_edges_plan (plan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan DAG edges';

CREATE TABLE IF NOT EXISTS agent_step_executions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_node_id INT NOT NULL,
    run_id INT NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1,
    worker_id VARCHAR(255) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    retry_reason VARCHAR(500) NULL,
    input_artifact_refs JSON NULL,
    output_artifact_refs JSON NULL,
    warning_codes JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_steps_node FOREIGN KEY (plan_node_id) REFERENCES agent_plan_nodes(id),
    CONSTRAINT fk_agent_steps_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_steps_attempt UNIQUE (plan_node_id, attempt_number),
    INDEX ix_agent_steps_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan node execution attempts';

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_node_id INT NULL,
    step_execution_id INT NULL,
    tool_name VARCHAR(128) NOT NULL,
    tool_version VARCHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    risk_level VARCHAR(32) NOT NULL DEFAULT 'safe_read',
    idempotency_key VARCHAR(255) NOT NULL,
    input_summary VARCHAR(4000) NULL,
    output_summary VARCHAR(4000) NULL,
    artifact_refs JSON NULL,
    warning_codes JSON NULL,
    error_code VARCHAR(100) NULL,
    latency_ms INT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_tool_calls_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT fk_agent_tool_calls_node FOREIGN KEY (plan_node_id) REFERENCES agent_plan_nodes(id),
    CONSTRAINT fk_agent_tool_calls_step FOREIGN KEY (step_execution_id) REFERENCES agent_step_executions(id),
    CONSTRAINT uq_agent_tool_calls_idempotency UNIQUE (idempotency_key),
    INDEX ix_agent_tool_calls_run_status (run_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent tool invocation records';

CREATE TABLE IF NOT EXISTS agent_artifacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_node_id INT NULL,
    step_execution_id INT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    summary VARCHAR(4000) NOT NULL,
    content_hash VARCHAR(64) NULL,
    content_json JSON NULL,
    sensitive_level VARCHAR(32) NOT NULL DEFAULT 'internal',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_artifacts_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_artifacts_run_type (run_id, artifact_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent large-object artifacts';

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    state_json JSON NOT NULL,
    event_sequence INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_checkpoints_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_checkpoints_run_created (run_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent durable checkpoints';

CREATE TABLE IF NOT EXISTS agent_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    sequence INT NOT NULL,
    state_version INT NOT NULL DEFAULT 0,
    event_type VARCHAR(64) NOT NULL,
    schema_version INT NOT NULL DEFAULT 1,
    trace_id VARCHAR(64) NULL,
    occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_json JSON NULL,
    CONSTRAINT fk_agent_events_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_events_run_sequence UNIQUE (run_id, sequence),
    INDEX ix_agent_events_run_sequence (run_id, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Replayable agent events';
