-- 041：持久化 Agent Run 的 Feature Flag 执行快照（additive only）。
-- 新创建的任务保存 loop / event schema / timeline 的最终解析值，避免后续工作区开关
-- 改写已经运行或已完成任务的历史执行事实；不修改、不删除任何既有记录。
ALTER TABLE agent_runs
    ADD COLUMN IF NOT EXISTS feature_flags_snapshot_json JSON NULL
    COMMENT 'Agent Run 创建时的完整功能开关快照';