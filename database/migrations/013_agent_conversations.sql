-- CyberGuard multi-turn conversation foundation (additive only).
-- Long-lived AgentConversation per project security task, one AgentTurn per
-- user input, and an idempotent message stream with client_message_id dedupe.
-- NOTE: agent_turns <-> agent_conversation_messages have a circular foreign key
-- dependency, so the input_message_id constraint is added via ALTER last.

CREATE TABLE IF NOT EXISTS agent_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    project_id INT NOT NULL,
    current_snapshot_id INT NULL,
    title VARCHAR(200) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    message_sequence INT NOT NULL DEFAULT 0,
    turn_sequence INT NOT NULL DEFAULT 0,
    context_version INT NOT NULL DEFAULT 0,
    summary_version INT NOT NULL DEFAULT 0,
    last_event_sequence INT NOT NULL DEFAULT 0,
    parent_conversation_id INT NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_conversations_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_agent_conversations_project FOREIGN KEY (project_id) REFERENCES security_projects(id),
    CONSTRAINT fk_agent_conversations_snapshot FOREIGN KEY (current_snapshot_id) REFERENCES project_snapshots(id),
    CONSTRAINT fk_agent_conversations_parent FOREIGN KEY (parent_conversation_id) REFERENCES agent_conversations(id),
    CONSTRAINT fk_agent_conversations_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_agent_conversations_workspace_created (workspace_id, created_at),
    INDEX ix_agent_conversations_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Long-lived agent workbench conversations';

CREATE TABLE IF NOT EXISTS agent_turns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    turn_sequence INT NOT NULL,
    run_id INT NULL,
    parent_turn_id INT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    input_message_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_turns_conversation FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_turns_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT fk_agent_turns_parent FOREIGN KEY (parent_turn_id) REFERENCES agent_turns(id),
    CONSTRAINT uq_agent_turns_conversation_seq UNIQUE (conversation_id, turn_sequence),
    INDEX ix_agent_turns_conversation (conversation_id),
    INDEX ix_agent_turns_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='One user input and its execution scope';

CREATE TABLE IF NOT EXISTS agent_conversation_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    turn_id INT NULL,
    client_message_id VARCHAR(64) NOT NULL,
    message_sequence INT NOT NULL,
    role VARCHAR(16) NOT NULL,
    message_type VARCHAR(32) NOT NULL DEFAULT 'user_goal',
    content_redacted TEXT NOT NULL,
    content_digest VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_conv_messages_conversation FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_messages_turn FOREIGN KEY (turn_id) REFERENCES agent_turns(id),
    CONSTRAINT uq_conv_messages_client UNIQUE (client_message_id),
    CONSTRAINT uq_conv_messages_sequence UNIQUE (conversation_id, message_sequence),
    INDEX ix_conv_messages_conversation_seq (conversation_id, message_sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Idempotent conversation message stream';

ALTER TABLE agent_turns
    ADD CONSTRAINT fk_agent_turns_input_message
    FOREIGN KEY (input_message_id) REFERENCES agent_conversation_messages(id);
