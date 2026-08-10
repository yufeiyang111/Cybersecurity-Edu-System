-- 持久记忆第二档：时间治理 + 反馈闭环（additive only）。
-- 1) user_memories 增加强化时间与过期时间；
-- 2) memory_feedback 反馈表（好/坏打标，负面计数驱动"建议删除"）。

ALTER TABLE user_memories
    ADD COLUMN last_reinforced_at DATETIME NULL COMMENT '最近被检索引用时间（强化）' AFTER updated_at,
    ADD COLUMN expires_at DATETIME NULL COMMENT '过期时间，NULL 表示永不过期' AFTER last_reinforced_at;

CREATE TABLE IF NOT EXISTS memory_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    memory_id INT NOT NULL,
    user_id INT NOT NULL,
    rating TINYINT NOT NULL COMMENT '1=有用 0=没用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_feedback_memory (memory_id),
    INDEX ix_memory_feedback_user (user_id),
    CONSTRAINT fk_memory_feedback_memory FOREIGN KEY (memory_id)
        REFERENCES user_memories (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_feedback_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆反馈';
