-- A8 工作区 Provider 策略：provider_allowlist / preferred_provider（additive only）
-- 迁移 033：工作区可限定允许的 LLM Provider 与首选 Provider；
-- 不保存任何 API Key / Base URL（密钥仍在用户配置与 env）。

ALTER TABLE workspaces
    ADD COLUMN provider_allowlist JSON NULL COMMENT '允许的 Provider 名称列表（空=不限制）',
    ADD COLUMN preferred_provider VARCHAR(64) NULL COMMENT '首选 Provider（须在 allowlist 内）';
