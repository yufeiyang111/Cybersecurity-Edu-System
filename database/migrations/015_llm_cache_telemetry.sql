-- CyberGuard LLM cache telemetry status on call logs (additive only).
ALTER TABLE llm_call_logs
    ADD COLUMN cache_status VARCHAR(16) NULL AFTER cached_input_tokens,
    ADD COLUMN cache_write_input_tokens INT NOT NULL DEFAULT 0 AFTER cache_status;
