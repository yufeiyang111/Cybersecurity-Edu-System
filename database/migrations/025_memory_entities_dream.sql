-- 持久记忆第三档：实体图谱 + Dream 后台整合（additive only）。
-- 1) memory_entities / memory_entity_links：记忆实体与实体间关系；
-- 2) memory_dream_audit：Dream 合成/取代/合并操作审计（可回滚）。

CREATE TABLE IF NOT EXISTS memory_entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    memory_id INT NULL,
    name VARCHAR(128) NOT NULL,
    entity_type VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT 'person/org/tech/other',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_entities_user_name (user_id, name),
    INDEX ix_memory_entities_memory (memory_id),
    CONSTRAINT fk_memory_entities_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_entities_memory FOREIGN KEY (memory_id)
        REFERENCES user_memories (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆实体';

CREATE TABLE IF NOT EXISTS memory_entity_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    source_entity_id INT NOT NULL,
    target_entity_id INT NOT NULL,
    relation VARCHAR(64) NOT NULL DEFAULT 'related',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_entity_links_source (source_entity_id),
    INDEX ix_memory_entity_links_target (target_entity_id),
    CONSTRAINT fk_memory_entity_links_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_entity_links_source FOREIGN KEY (source_entity_id)
        REFERENCES memory_entities (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_entity_links_target FOREIGN KEY (target_entity_id)
        REFERENCES memory_entities (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆实体关系';

CREATE TABLE IF NOT EXISTS memory_dream_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(32) NOT NULL COMMENT 'synthesize/supersede/merge',
    memory_ids VARCHAR(512) NULL COMMENT '被处理记忆 id 列表（逗号分隔）',
    detail VARCHAR(2000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_dream_audit_user (user_id, created_at),
    CONSTRAINT fk_memory_dream_audit_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dream 记忆整合审计';
