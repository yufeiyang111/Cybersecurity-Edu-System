-- LLM Provider 支持自定义 max_tokens（additive only）。
-- NULL 表示使用全局默认值（LLMRequest.max_tokens = 2048）。

ALTER TABLE llm_provider_configs
    ADD COLUMN max_tokens INT NULL COMMENT '自定义最大输出 tokens，NULL 使用默认 2048';
