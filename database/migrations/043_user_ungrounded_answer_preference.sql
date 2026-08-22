-- Persist the opt-in for model-only answers when public RAG finds no evidence.
ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS allow_ungrounded_answers BOOLEAN NOT NULL DEFAULT FALSE
    COMMENT '无可验证知识库证据时允许基于模型通用知识回答';
