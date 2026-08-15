-- 038：Enterprise RAG Core 的可追溯版本、脱敏检索 trace 与离线评测结构（additive only）。
-- 约束：本迁移不保存原 query、文档正文、Prompt、provider 原始 CoT、Authorization 或 Token。

CREATE TABLE IF NOT EXISTS rag_pipeline_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version_key VARCHAR(64) NOT NULL,
    config_json JSON NOT NULL,
    prompt_version VARCHAR(64) NOT NULL,
    embedding_version VARCHAR(255) NOT NULL,
    reranker_version VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rag_pipeline_versions_key (version_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Enterprise RAG pipeline versions';

CREATE TABLE IF NOT EXISTS rag_retrieval_traces (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(64) NULL,
    record_id INT NULL,
    user_id INT NOT NULL,
    pipeline_version_id INT NULL,
    query_fingerprint VARCHAR(64) NOT NULL,
    stage_summary_json JSON NOT NULL,
    warnings_json JSON NULL,
    retrieval_ms INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rag_retrieval_traces_record
        FOREIGN KEY (record_id) REFERENCES qa_records(id) ON DELETE SET NULL,
    CONSTRAINT fk_rag_retrieval_traces_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_rag_retrieval_traces_pipeline_version
        FOREIGN KEY (pipeline_version_id) REFERENCES rag_pipeline_versions(id) ON DELETE SET NULL,
    INDEX ix_rag_retrieval_traces_user_time (user_id, created_at),
    INDEX ix_rag_retrieval_traces_record (record_id),
    INDEX ix_rag_retrieval_traces_request (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Redacted RAG retrieval traces';

CREATE TABLE IF NOT EXISTS rag_evaluation_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipeline_version_id INT NULL,
    corpus_version VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    metrics_json JSON NULL,
    report_path VARCHAR(500) NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME NULL,
    CONSTRAINT fk_rag_evaluation_runs_pipeline_version
        FOREIGN KEY (pipeline_version_id) REFERENCES rag_pipeline_versions(id) ON DELETE SET NULL,
    INDEX ix_rag_evaluation_runs_status_time (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Enterprise RAG evaluation runs';

CREATE TABLE IF NOT EXISTS rag_evaluation_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    case_id BIGINT UNSIGNED NOT NULL,
    retrieval_metrics_json JSON NULL,
    citation_metrics_json JSON NULL,
    answer_metrics_json JSON NULL,
    failure_stage VARCHAR(64) NULL,
    notes VARCHAR(1000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rag_evaluation_results_run
        FOREIGN KEY (run_id) REFERENCES rag_evaluation_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_rag_evaluation_results_case
        FOREIGN KEY (case_id) REFERENCES rag_eval_cases(id) ON DELETE CASCADE,
    UNIQUE KEY uq_rag_evaluation_results_run_case (run_id, case_id),
    INDEX ix_rag_evaluation_results_failure_stage (failure_stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Enterprise RAG evaluation case results';

ALTER TABLE qa_records
    ADD COLUMN IF NOT EXISTS answer_status VARCHAR(32) NULL COMMENT 'RAG 回答证据状态';

ALTER TABLE qa_records
    ADD COLUMN IF NOT EXISTS citation_manifest_json JSON NULL COMMENT '结构化 citation manifest（不含正文）';

ALTER TABLE qa_records
    ADD COLUMN IF NOT EXISTS rag_trace_id INT NULL COMMENT '脱敏检索 trace ID';

ALTER TABLE qa_records
    ADD COLUMN IF NOT EXISTS pipeline_version_key VARCHAR(64) NULL COMMENT 'RAG pipeline version key';

ALTER TABLE rag_eval_cases
    ADD COLUMN IF NOT EXISTS expected_evidence_json JSON NULL COMMENT '期望证据文档与行号标签';

ALTER TABLE rag_eval_cases
    ADD COLUMN IF NOT EXISTS expected_status VARCHAR(32) NULL COMMENT '期望回答证据状态';

ALTER TABLE rag_eval_cases
    ADD COLUMN IF NOT EXISTS difficulty VARCHAR(32) NULL COMMENT '评测难度';

ALTER TABLE rag_eval_cases
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否纳入当前评测';

ALTER TABLE rag_eval_cases
    ADD COLUMN IF NOT EXISTS updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP COMMENT '评测标签最后更新时间';