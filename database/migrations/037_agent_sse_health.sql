-- 037：Agent SSE 健康统计（additive only）。
-- 记录带水位重连（Last-Event-ID > 0）与 replay gap（AGENT_SSE_REPLAY_GAP 错误帧），
-- 用于 spec §19.3 的 SSE 重连/Gap/Resync 率指标聚合。纯统计表，不参与业务状态机。

CREATE TABLE IF NOT EXISTS agent_sse_health (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    run_id INT NOT NULL,
    event_type VARCHAR(32) NOT NULL COMMENT 'connect_with_watermark / replay_gap',
    last_event_id INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_agent_sse_health_ws_time (workspace_id, created_at),
    INDEX ix_agent_sse_health_run (run_id),
    CONSTRAINT fk_agent_sse_health_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent SSE reconnect and replay gap health';
