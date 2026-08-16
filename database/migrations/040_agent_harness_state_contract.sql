-- 040：Agent Harness V2 状态契约（additive only）。
-- 扩展 agent_runs.status 枚举以记录可审计的取消收尾与可恢复的证据阻塞。
-- 不删除、不重置、不修改已有任务、计划、工具调用或审计数据。

ALTER TABLE agent_runs
    MODIFY COLUMN status ENUM(
        'created',
        'queued',
        'preparing',
        'mapping_repository',
        'planning',
        'validating_plan',
        'executing_tools',
        'evaluating_evidence',
        'replanning',
        'deep_reviewing',
        'awaiting_approval',
        'paused',
        'generating_report',
        'completed',
        'completed_with_warnings',
        'blocked',
        'cancel_requested',
        'partial',
        'failed',
        'canceled'
    ) NOT NULL DEFAULT 'created';