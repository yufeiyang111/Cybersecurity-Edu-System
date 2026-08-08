-- CyberGuard RAG retrieval logging + offline evaluation set (additive only).

-- 每次 QA 检索的落库日志：用于离线评估检索质量与事后分析
CREATE TABLE IF NOT EXISTS qa_retrieval_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NOT NULL,
    query TEXT NOT NULL,
    conversation_id INT UNSIGNED NULL,
    record_id BIGINT UNSIGNED NULL,
    engine_version VARCHAR(64) NOT NULL DEFAULT 'enhanced',
    model_name VARCHAR(64) NULL,
    retrieved_docs JSON NULL COMMENT '检索命中的文档(含doc_id/title/similarity/行号)',
    sources JSON NULL COMMENT '最终引用来源',
    retrieval_ms INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_retrieval_logs_user (user_id, created_at),
    KEY idx_retrieval_logs_record (record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 离线评估集：查询 + 期望命中的文档 + 期望答案（ground truth）
CREATE TABLE IF NOT EXISTS rag_eval_cases (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    query VARCHAR(500) NOT NULL,
    expected_doc_ids JSON NOT NULL COMMENT '期望命中的知识条目 id 列表',
    expected_answer TEXT NULL COMMENT '期望答案要点（用于答案相关性评估）',
    category VARCHAR(64) NULL,
    notes VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_eval_cases_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
