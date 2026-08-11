-- A5 计划重规划能力：决策记录表 + 节点输入参数 + run 重规划计数（additive only）
-- 迁移 030：agent_decision_records / agent_plan_nodes.input_json / agent_runs.replan_count

CREATE TABLE IF NOT EXISTS agent_decision_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    supersedes_version INT NULL,
    reason_code VARCHAR(64) NOT NULL,
    decision_type VARCHAR(32) NOT NULL,
    detail_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_decision_records_run
        FOREIGN KEY (run_id) REFERENCES agent_runs (id) ON DELETE CASCADE,
    INDEX ix_agent_decision_records_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- replan 新增节点可携带工具输入参数（如 search_code 的 query、get_related_files 的 file_path）
ALTER TABLE agent_plan_nodes
    ADD COLUMN input_json JSON NULL COMMENT '节点工具的输入参数（A5 replan 节点使用）';

-- 重规划次数硬限制（避免无限 replan 循环）
ALTER TABLE agent_runs
    ADD COLUMN replan_count INT NOT NULL DEFAULT 0 COMMENT '已完成的重规划次数';
