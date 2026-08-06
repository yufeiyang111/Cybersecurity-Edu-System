-- CyberGuard agent-run LLM invocations and versioned price catalog (additive only).
CREATE TABLE IF NOT EXISTS llm_invocations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    step_execution_id INT NULL,
    workspace_id INT NOT NULL,
    user_id INT NULL,
    provider_config_id INT NULL,
    provider_name VARCHAR(128) NOT NULL,
    model VARCHAR(200),
    model_version VARCHAR(64),
    operation VARCHAR(64) NOT NULL DEFAULT 'unknown',
    prompt_template_version VARCHAR(64),
    input_digest VARCHAR(64),
    output_digest VARCHAR(64),
    status VARCHAR(32) NOT NULL,
    warning_code VARCHAR(100),
    latency_ms INT NULL,
    first_token_latency_ms INT NULL,
    input_tokens INT NOT NULL DEFAULT 0,
    cached_input_tokens INT NOT NULL DEFAULT 0,
    cache_creation_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    usage_source VARCHAR(24) NOT NULL DEFAULT 'unknown',
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    input_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    cached_input_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    output_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    reasoning_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    pricing_version VARCHAR(64),
    provider_cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    application_cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_llm_invocations_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_llm_invocations_step FOREIGN KEY (step_execution_id) REFERENCES agent_step_executions(id) ON DELETE SET NULL,
    CONSTRAINT fk_llm_invocations_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_llm_invocations_provider FOREIGN KEY (provider_config_id) REFERENCES llm_provider_configs(id) ON DELETE SET NULL,
    INDEX ix_llm_invocations_run_created (run_id, created_at),
    INDEX ix_llm_invocations_workspace_created (workspace_id, created_at),
    INDEX ix_llm_invocations_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Per-invocation agent LLM usage and cost audit';

CREATE TABLE IF NOT EXISTS llm_price_catalog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider_name VARCHAR(128) NOT NULL,
    model VARCHAR(200) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    effective_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    input_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    cached_input_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    output_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    reasoning_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    pricing_version VARCHAR(64) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'builtin',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_llm_price_catalog_entry UNIQUE (provider_name, model, currency, pricing_version),
    INDEX ix_llm_price_catalog_model (model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned per-million-token price snapshots';

-- Built-in estimated prices (USD per million tokens); real prices are snapshotted by
-- future admin flows. Costs computed from this catalog are flagged usage_source=estimated.
INSERT IGNORE INTO llm_price_catalog
    (provider_name, model, currency, input_price_per_million, cached_input_price_per_million, output_price_per_million, reasoning_price_per_million, pricing_version, source)
VALUES
    ('deepseek-chat', 'deepseek-chat', 'USD', 0.270000, 0.027000, 1.100000, 0.000000, 'builtin-v1', 'builtin'),
    ('deepseek-reasoner', 'deepseek-reasoner', 'USD', 0.550000, 0.055000, 2.190000, 0.000000, 'builtin-v1', 'builtin'),
    ('gpt-4o-mini', 'gpt-4o-mini', 'USD', 0.150000, 0.075000, 0.600000, 0.000000, 'builtin-v1', 'builtin'),
    ('gpt-4o', 'gpt-4o', 'USD', 2.500000, 1.250000, 10.000000, 0.000000, 'builtin-v1', 'builtin'),
    ('glm-4-plus', 'glm-4-plus', 'USD', 0.700000, 0.070000, 1.400000, 0.000000, 'builtin-v1', 'builtin'),
    ('minimax', 'MiniMax-Text-01', 'USD', 0.200000, 0.020000, 1.100000, 0.000000, 'builtin-v1', 'builtin');
