-- CyberGuard trusted agent RAG remediation persistence (additive migration).
-- Stores governed knowledge metadata and human-reviewable remediation outputs only.

CREATE TABLE IF NOT EXISTS security_knowledge_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    source_uri VARCHAR(2048) NULL,
    license_name VARCHAR(255) NULL,
    source_version VARCHAR(255) NOT NULL,
    content_hash VARCHAR(128) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSON NULL,
    published_at DATETIME NULL,
    effective_from DATETIME NULL,
    effective_until DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_security_knowledge_sources_workspace FOREIGN KEY (workspace_id)
        REFERENCES workspaces(id) ON DELETE CASCADE,
    INDEX ix_security_knowledge_sources_workspace_active (workspace_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Governed workspace security knowledge sources';

CREATE TABLE IF NOT EXISTS security_knowledge_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL,
    document_version VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT NULL,
    tags_json JSON NULL,
    framework_metadata_json JSON NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from DATETIME NULL,
    effective_until DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_knowledge_source_document_version UNIQUE (source_id, document_version),
    CONSTRAINT fk_security_knowledge_documents_source FOREIGN KEY (source_id)
        REFERENCES security_knowledge_sources(id) ON DELETE CASCADE,
    INDEX ix_security_knowledge_documents_source_active (source_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned security knowledge documents';

CREATE TABLE IF NOT EXISTS remediation_suggestions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    finding_id INT NOT NULL,
    rationale TEXT NOT NULL,
    remediation_steps_json JSON NOT NULL,
    patch_diff TEXT NULL,
    citations_json JSON NULL,
    warning_codes_json JSON NULL,
    provider VARCHAR(128) NOT NULL,
    model VARCHAR(255) NULL,
    model_version VARCHAR(255) NULL,
    confidence FLOAT NULL,
    review_state ENUM('pending', 'accepted', 'rejected', 'needs_revision') NOT NULL DEFAULT 'pending',
    reviewer_id INT NULL,
    reviewed_at DATETIME NULL,
    review_comment TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_remediation_suggestion_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT fk_remediation_suggestions_finding FOREIGN KEY (finding_id)
        REFERENCES security_findings(id) ON DELETE CASCADE,
    CONSTRAINT fk_remediation_suggestions_reviewer FOREIGN KEY (reviewer_id)
        REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_remediation_suggestions_finding_created (finding_id, created_at),
    INDEX ix_remediation_suggestions_review_state (review_state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Human-reviewable remediation suggestions';
