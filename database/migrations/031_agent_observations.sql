-- A6 Deep Review 观察结论：agent_observations 三表（additive only）
-- 迁移 031：Agent 深度审查产出结构化观察（默认 unverified），
-- 含受影响位置（locations）与 RAG 引用（citations，含注入标记与摘要指纹）

CREATE TABLE IF NOT EXISTS agent_observations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    status ENUM('unverified', 'confirmed', 'rejected', 'needs_more_evidence') NOT NULL DEFAULT 'unverified',
    cwe_id VARCHAR(32) NULL,
    confidence VARCHAR(16) NOT NULL DEFAULT 'low',
    summary TEXT NOT NULL,
    detail_json JSON NULL COMMENT '证据链/风险影响/修复方向',
    proof_gaps_json JSON NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'deep_review',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_observations_run
        FOREIGN KEY (run_id) REFERENCES agent_runs (id) ON DELETE CASCADE,
    INDEX ix_agent_observations_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent Deep Review 观察结论';

CREATE TABLE IF NOT EXISTS agent_observation_locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    observation_id INT NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    start_line INT NOT NULL,
    end_line INT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'evidence',
    CONSTRAINT fk_agent_obs_locations_obs
        FOREIGN KEY (observation_id) REFERENCES agent_observations (id) ON DELETE CASCADE,
    INDEX ix_agent_obs_locations_obs (observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='观察结论受影响位置';

CREATE TABLE IF NOT EXISTS agent_observation_citations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    observation_id INT NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'rag',
    document_id VARCHAR(255) NULL,
    document_title VARCHAR(500) NULL,
    trust_score FLOAT NULL,
    injection_flags JSON NULL,
    content_digest VARCHAR(64) NOT NULL,
    quote_preview VARCHAR(2000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_obs_citations_obs
        FOREIGN KEY (observation_id) REFERENCES agent_observations (id) ON DELETE CASCADE,
    INDEX ix_agent_obs_citations_obs (observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='观察结论 RAG 引用（含注入标记）';
