-- QA 回答最大输出 Tokens 用户设置（additive only）。
-- NULL 表示使用引擎默认（16384）；数值范围 256 ~ 32768。

ALTER TABLE user_preferences
    ADD COLUMN qa_max_tokens INT NULL COMMENT 'QA 回答最大输出 tokens，NULL 使用引擎默认 16384';
