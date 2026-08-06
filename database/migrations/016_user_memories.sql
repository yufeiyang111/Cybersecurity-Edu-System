-- CyberGuard persistent user memory (additive only).
-- Modeled after Mem0's user-scoped memory layer: facts extracted from QA
-- interactions, retrieved by semantic similarity before each answer.
CREATE TABLE IF NOT EXISTS user_memories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content VARCHAR(2000) NOT NULL,
    category VARCHAR(32) NOT NULL DEFAULT 'fact',
    source_conversation_id INT NULL,
    source_record_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_memories_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_memories_record FOREIGN KEY (source_record_id) REFERENCES qa_records(id) ON DELETE SET NULL,
    INDEX ix_user_memories_user_created (user_id, created_at),
    INDEX ix_user_memories_user_category (user_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User-scoped persistent memories extracted from QA';

ALTER TABLE user_preferences
    ADD COLUMN persistent_memory_enabled BOOLEAN NOT NULL DEFAULT FALSE AFTER show_security_warnings;
