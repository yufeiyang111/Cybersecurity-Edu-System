-- CyberGuard project cascade delete: allow deleting projects that have
-- Agent conversations or runs by cascade rather than rejection.
--
-- Chain of FKs from project -> agent_runs -> agent_messages/plans/etc:
--   agent_runs.project_id     → CASCADE  (was RESTRICT)
--   agent_runs.snapshot_id    → CASCADE  (was RESTRICT)  ← 快照删除时级联清理 AgentRun
--   agent_messages.run_id     → CASCADE  (was RESTRICT)
--   agent_plans.run_id        → CASCADE  (was RESTRICT)
--   agent_step_executions.run_id → CASCADE (was RESTRICT)
--   agent_tool_calls.run_id   → CASCADE  (was RESTRICT)
--   agent_artifacts.run_id    → CASCADE  (was RESTRICT)
--   agent_checkpoints.run_id  → CASCADE  (was RESTRICT)
--   agent_events.run_id       → CASCADE  (was RESTRICT)
--   agent_turns.run_id        → CASCADE  (was RESTRICT)
--   agent_conversations.project_id       → CASCADE (was RESTRICT)
--   agent_conversations.current_snapshot_id → SET NULL (was RESTRICT)

ALTER TABLE agent_runs
    DROP FOREIGN KEY fk_agent_runs_project,
    ADD CONSTRAINT fk_agent_runs_project
        FOREIGN KEY (project_id) REFERENCES security_projects(id) ON DELETE CASCADE;

ALTER TABLE agent_runs
    DROP FOREIGN KEY fk_agent_runs_snapshot,
    ADD CONSTRAINT fk_agent_runs_snapshot
        FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE;

ALTER TABLE agent_messages
    DROP FOREIGN KEY fk_agent_messages_run,
    ADD CONSTRAINT fk_agent_messages_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_plans
    DROP FOREIGN KEY fk_agent_plans_run,
    ADD CONSTRAINT fk_agent_plans_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_step_executions
    DROP FOREIGN KEY fk_agent_steps_run,
    ADD CONSTRAINT fk_agent_steps_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_tool_calls
    DROP FOREIGN KEY fk_agent_tool_calls_run,
    ADD CONSTRAINT fk_agent_tool_calls_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_artifacts
    DROP FOREIGN KEY fk_agent_artifacts_run,
    ADD CONSTRAINT fk_agent_artifacts_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_checkpoints
    DROP FOREIGN KEY fk_agent_checkpoints_run,
    ADD CONSTRAINT fk_agent_checkpoints_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_events
    DROP FOREIGN KEY fk_agent_events_run,
    ADD CONSTRAINT fk_agent_events_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_turns
    DROP FOREIGN KEY fk_agent_turns_run,
    ADD CONSTRAINT fk_agent_turns_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE;

ALTER TABLE agent_conversations
    DROP FOREIGN KEY fk_agent_conversations_project,
    ADD CONSTRAINT fk_agent_conversations_project
        FOREIGN KEY (project_id) REFERENCES security_projects(id) ON DELETE CASCADE;

ALTER TABLE agent_conversations
    DROP FOREIGN KEY fk_agent_conversations_snapshot,
    ADD CONSTRAINT fk_agent_conversations_snapshot
        FOREIGN KEY (current_snapshot_id) REFERENCES project_snapshots(id) ON DELETE SET NULL;
