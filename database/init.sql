-- =========================================
-- CyberGuard 网络安全智能问答教学系统
-- 数据库初始化脚本
-- =========================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS cyberguard
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE cyberguard;

-- =========================================
-- 用户角色表
-- =========================================
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '角色名称',
    description VARCHAR(200) COMMENT '角色描述',
    permissions JSON COMMENT '权限列表',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户角色表';

-- 初始化角色
INSERT INTO roles (name, description, permissions) VALUES
('admin', '系统管理员', '["all"]'),
('teacher', '教师用户', '["knowledge:create", "knowledge:edit", "knowledge:delete", "qa:review"]'),
('user', '普通用户', '["qa:ask", "qa:history", "favorite:manage"]'),
('guest', '游客', '["knowledge:view"]')
ON DUPLICATE KEY UPDATE 
    description = VALUES(description),
    permissions = VALUES(permissions);

-- =========================================
-- 用户表
-- =========================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    email VARCHAR(100) UNIQUE COMMENT '邮箱',
    password_hash VARCHAR(255) COMMENT '密码哈希',
    nickname VARCHAR(50) COMMENT '昵称',
    avatar_url VARCHAR(255) COMMENT '头像URL',
    oauth_provider VARCHAR(20) COMMENT '第三方登录提供商',
    oauth_subject VARCHAR(100) COMMENT '第三方账号唯一标识',
    oauth_bindings TEXT COMMENT '全部第三方绑定 JSON 数组',
    role_id INT NOT NULL DEFAULT 3 COMMENT '角色ID',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    last_login_at DATETIME COMMENT '最后登录时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_oauth (oauth_provider, oauth_subject),
    FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- =========================================
-- 默认测试用户（密码均为 123456，使用 bcrypt 加密）
-- 注意：以下哈希值对应的密码均为 "123456"
-- =========================================
INSERT INTO users (username, email, password_hash, nickname, role_id) VALUES
('admin', 'admin@cyberguard.local', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '管理员', 1),
('teacher', 'teacher@cyberguard.local', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '教师', 2),
('user', 'user@cyberguard.local', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '用户', 3)
ON DUPLICATE KEY UPDATE 
    nickname = VALUES(nickname),
    role_id = VALUES(role_id);


-- =========================================
-- 登录日志表
-- =========================================
CREATE TABLE IF NOT EXISTS login_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT COMMENT '用户ID',
    ip_address VARCHAR(50) COMMENT 'IP地址',
    user_agent VARCHAR(255) COMMENT '用户代理',
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('success', 'failed') DEFAULT 'success' COMMENT '登录状态',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录日志表';

-- =========================================
-- 知识分类表
-- =========================================
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '分类名称',
    description TEXT COMMENT '分类描述',
    parent_id INT DEFAULT NULL COMMENT '父分类ID',
    icon VARCHAR(50) COMMENT '图标名称',
    sort_order INT DEFAULT 0 COMMENT '排序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识分类表';

-- 初始化知识分类
INSERT INTO categories (name, description, icon, sort_order) VALUES
('网络安全基础', '网络基本原理和安全概念', 'Connection', 1),
('Web 安全', 'Web 应用漏洞与防护', 'Monitor', 2),
('系统安全', '操作系统安全加固', 'Desktop', 3),
('密码学', '加密算法与安全协议', 'Key', 4),
('渗透测试', '渗透测试方法与工具', 'Aim', 5),
('应急响应', '安全事件响应取证', 'Warning', 6),
('数据安全', '数据保护隐私合规', 'Folder', 7),
('移动安全', '移动应用设备安全', 'Mobile', 8)
ON DUPLICATE KEY UPDATE 
    description = VALUES(description),
    icon = VALUES(icon),
    sort_order = VALUES(sort_order);

-- =========================================
-- 知识条目表
-- =========================================
CREATE TABLE IF NOT EXISTS knowledge_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL COMMENT '标题',
    content TEXT NOT NULL COMMENT '内容',
    summary TEXT COMMENT '摘要',
    category_id INT COMMENT '分类ID',
    difficulty ENUM('easy', 'medium', 'hard') DEFAULT 'medium' COMMENT '难度',
    source VARCHAR(200) COMMENT '来源',
    author_id INT COMMENT '作者ID',
    view_count INT DEFAULT 0 COMMENT '浏览次数',
    favorite_count INT DEFAULT 0 COMMENT '收藏次数',
    status ENUM('draft', 'published', 'archived') DEFAULT 'published' COMMENT '状态',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL,
    FULLTEXT INDEX idx_fulltext (title, content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识条目表';

-- =========================================
-- 知识标签关联表
-- =========================================
CREATE TABLE IF NOT EXISTS knowledge_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    knowledge_id INT NOT NULL COMMENT '知识ID',
    tag_name VARCHAR(50) NOT NULL COMMENT '标签名',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    UNIQUE KEY unique_knowledge_tag (knowledge_id, tag_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识标签关联表';

-- =========================================
-- 问答会话表
-- =========================================
CREATE TABLE IF NOT EXISTS qa_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    title VARCHAR(200) COMMENT '会话标题',
    is_archived BOOLEAN DEFAULT FALSE COMMENT '是否归档',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问答会话表';

-- =========================================
-- 问答记录表
-- =========================================
CREATE TABLE IF NOT EXISTS qa_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT COMMENT '会话ID',
    user_id INT NOT NULL COMMENT '用户ID',
    question TEXT NOT NULL COMMENT '问题',
    answer TEXT COMMENT '答案',
    sources JSON COMMENT '来源信息',
    confidence FLOAT COMMENT '置信度',
    model_name VARCHAR(50) COMMENT '使用的模型',
    response_time FLOAT COMMENT '响应时间(秒)',
    feedback ENUM('good', 'neutral', 'bad') COMMENT '用户反馈',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES qa_conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FULLTEXT INDEX idx_fulltext_question (question)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问答记录表';

-- =========================================
-- 收藏表
-- =========================================
CREATE TABLE IF NOT EXISTS favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    qa_record_id INT NOT NULL COMMENT '问答记录ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (qa_record_id) REFERENCES qa_records(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_qa (user_id, qa_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏表';

-- =========================================
-- 追问建议表
-- =========================================
CREATE TABLE IF NOT EXISTS suggested_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question VARCHAR(500) NOT NULL COMMENT '问题',
    suggestions JSON COMMENT '建议列表',
    category VARCHAR(100) COMMENT '分类',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='追问建议表';

-- =========================================
-- 系统配置表
-- =========================================
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    description VARCHAR(200) COMMENT '配置描述',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';

-- 初始化系统配置
INSERT INTO system_configs (config_key, config_value, description) VALUES
('llm_api_key', '', '通义千问 API 密钥'),
('llm_model', 'qwen-plus', '使用的 LLM 模型'),
('vector_top_k', '10', '向量检索返回数量'),
('similarity_threshold', '0.5', '相似度阈值'),
('max_context_length', '4000', '最大上下文长度')
ON DUPLICATE KEY UPDATE 
    config_value = VALUES(config_value),
    description = VALUES(description);

-- =========================================
-- 知识图谱关系表
-- =========================================
CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT '源节点ID',
    target_id INT NOT NULL COMMENT '目标节点ID',
    relation_type VARCHAR(50) NOT NULL COMMENT '关系类型',
    weight FLOAT DEFAULT 1.0 COMMENT '权重',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    UNIQUE KEY unique_edge (source_id, target_id, relation_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识图谱关系表';

-- =========================================
-- 反馈记录表
-- =========================================
CREATE TABLE IF NOT EXISTS feedback_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    qa_record_id INT NOT NULL COMMENT '问答记录ID',
    user_id INT NOT NULL COMMENT '用户ID',
    feedback_type ENUM('good', 'neutral', 'bad') COMMENT '反馈类型',
    comment TEXT COMMENT '反馈评论',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qa_record_id) REFERENCES qa_records(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='反馈记录表';

-- =========================================
-- 创建索引以优化查询性能
-- =========================================
DROP INDEX IF EXISTS idx_users_email ON users;
DROP INDEX IF EXISTS idx_users_username ON users;
DROP INDEX IF EXISTS idx_knowledge_category ON knowledge_items;
DROP INDEX IF EXISTS idx_knowledge_created ON knowledge_items;
DROP INDEX IF EXISTS idx_qa_user ON qa_records;
DROP INDEX IF EXISTS idx_qa_conversation ON qa_records;
DROP INDEX IF EXISTS idx_qa_created ON qa_records;
DROP INDEX IF EXISTS idx_favorites_user ON favorites;

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_knowledge_category ON knowledge_items(category_id);
CREATE INDEX idx_knowledge_created ON knowledge_items(created_at);
CREATE INDEX idx_qa_user ON qa_records(user_id);
CREATE INDEX idx_qa_conversation ON qa_records(conversation_id);
CREATE INDEX idx_qa_created ON qa_records(created_at);
CREATE INDEX idx_favorites_user ON favorites(user_id);

-- =========================================
-- 企业安全扫描基础表（与数据库迁移保持一致）
-- =========================================
-- CyberGuard security scanning foundation (additive migration)
-- Apply to an existing MySQL 8+ CyberGuard database. This migration does not alter or delete legacy tables.

CREATE TABLE IF NOT EXISTS workspaces (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspaces_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全工作区';

CREATE TABLE IF NOT EXISTS workspace_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    user_id INT NOT NULL,
    role ENUM('owner', 'security_admin', 'analyst', 'developer', 'viewer') NOT NULL DEFAULT 'viewer',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspace_membership UNIQUE (workspace_id, user_id),
    CONSTRAINT fk_workspace_members_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_workspace_members_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_workspace_members_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作区成员';

CREATE TABLE IF NOT EXISTS security_projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT NULL,
    default_branch VARCHAR(255) NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspace_project_name UNIQUE (workspace_id, name),
    CONSTRAINT fk_security_projects_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_security_projects_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_security_projects_workspace_id (workspace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全扫描项目';

CREATE TABLE IF NOT EXISTS project_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    source_type ENUM('zip', 'github') NOT NULL,
    source_ref VARCHAR(2048) NULL,
    commit_sha VARCHAR(128) NULL,
    content_sha256 CHAR(64) NOT NULL,
    storage_path VARCHAR(1024) NULL,
    file_count INT NOT NULL DEFAULT 0,
    total_bytes BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_project_snapshot_content UNIQUE (project_id, content_sha256),
    CONSTRAINT fk_project_snapshots_project FOREIGN KEY (project_id) REFERENCES security_projects(id) ON DELETE CASCADE,
    INDEX ix_project_snapshots_project_id (project_id),
    INDEX ix_project_snapshots_commit_sha (commit_sha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='不可变项目快照';

CREATE TABLE IF NOT EXISTS scan_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    status ENUM('created', 'validating', 'snapshotting', 'scanning', 'completed', 'completed_with_warnings', 'failed', 'canceled') NOT NULL DEFAULT 'created',
    progress INT NOT NULL DEFAULT 0,
    policy_version VARCHAR(100) NULL,
    worker_id VARCHAR(255) NULL,
    dispatch_key VARCHAR(64) NULL,
    retry_count INT NOT NULL DEFAULT 0,
    error_code VARCHAR(100) NULL,
    error_message TEXT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    canceled_at DATETIME NULL,
    summary_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_scan_tasks_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE,
    INDEX ix_scan_tasks_snapshot_id (snapshot_id),
    INDEX ix_scan_tasks_status (status),
    CONSTRAINT uq_scan_tasks_dispatch_key UNIQUE (dispatch_key),
    INDEX ix_scan_tasks_dispatch_key (dispatch_key),
    INDEX ix_scan_tasks_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='异步扫描任务';

CREATE TABLE IF NOT EXISTS security_findings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    fingerprint VARCHAR(128) NOT NULL,
    rule_id VARCHAR(128) NOT NULL,
    category ENUM('sast', 'secret', 'sca', 'configuration') NOT NULL,
    severity ENUM('critical', 'high', 'medium', 'low', 'info') NOT NULL,
    status ENUM('open', 'triaged', 'accepted_risk', 'false_positive', 'resolved') NOT NULL DEFAULT 'open',
    cwe_id VARCHAR(32) NULL,
    cve_id VARCHAR(32) NULL,
    file_path VARCHAR(1024) NOT NULL,
    start_line INT NOT NULL,
    end_line INT NULL,
    message TEXT NOT NULL,
    confidence FLOAT NULL,
    rule_version VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_task_finding_fingerprint UNIQUE (task_id, fingerprint),
    CONSTRAINT fk_security_findings_task FOREIGN KEY (task_id) REFERENCES scan_tasks(id) ON DELETE CASCADE,
    INDEX ix_security_findings_task_id (task_id),
    INDEX ix_security_findings_severity (severity),
    INDEX ix_security_findings_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准化安全发现项';

CREATE TABLE IF NOT EXISTS finding_evidences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    finding_id INT NOT NULL,
    evidence_type ENUM('code', 'secret', 'dependency', 'configuration', 'rag_reference') NOT NULL,
    content_redacted TEXT NOT NULL,
    secret_hash VARCHAR(128) NULL,
    source_uri VARCHAR(2048) NULL,
    start_line INT NULL,
    end_line INT NULL,
    score FLOAT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_finding_evidences_finding FOREIGN KEY (finding_id) REFERENCES security_findings(id) ON DELETE CASCADE,
    INDEX ix_finding_evidences_finding_id (finding_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='脱敏漏洞证据';

CREATE TABLE IF NOT EXISTS audit_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    actor_id INT NULL,
    action VARCHAR(128) NOT NULL,
    target_type VARCHAR(128) NOT NULL,
    target_id INT NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_events_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_events_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_audit_events_workspace_created (workspace_id, created_at),
    INDEX ix_audit_events_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全域审计事件';

-- Additive Phase 2 dependency inventory and advisory-cache persistence.

CREATE TABLE IF NOT EXISTS snapshot_dependencies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    ecosystem VARCHAR(64) NOT NULL,
    package_name VARCHAR(512) NOT NULL,
    version VARCHAR(255) NOT NULL,
    manifest_path VARCHAR(1024) NOT NULL,
    coordinate_hash VARCHAR(64) NOT NULL,
    is_direct BOOLEAN NOT NULL DEFAULT TRUE,
    source_line INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_snapshot_dependency_coordinate UNIQUE (
        snapshot_id, coordinate_hash
    ),
    CONSTRAINT fk_snapshot_dependencies_snapshot FOREIGN KEY (snapshot_id)
        REFERENCES project_snapshots(id) ON DELETE CASCADE,
    INDEX ix_snapshot_dependencies_snapshot_id (snapshot_id),
    INDEX ix_snapshot_dependencies_coordinate_hash (coordinate_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快照依赖库存';

CREATE TABLE IF NOT EXISTS vulnerability_advisory_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cache_key VARCHAR(128) NOT NULL,
    ecosystem VARCHAR(64) NOT NULL,
    package_name VARCHAR(512) NOT NULL,
    version VARCHAR(255) NOT NULL,
    response_json JSON NULL,
    fetched_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_vulnerability_advisory_cache_key UNIQUE (cache_key),
    INDEX ix_vulnerability_advisory_cache_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='漏洞公告缓存';

-- Additive Phase 3 trusted-agent RAG remediation persistence.

CREATE TABLE IF NOT EXISTS security_knowledge_sources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    source_uri VARCHAR(2048) NULL,
    license_name VARCHAR(255) NULL,
    source_version VARCHAR(255) NOT NULL,
    content_hash VARCHAR(128) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSON NULL,
    published_at DATETIME NULL,
    effective_from DATETIME NULL,
    effective_until DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_security_knowledge_sources_workspace FOREIGN KEY (workspace_id)
        REFERENCES workspaces(id) ON DELETE CASCADE,
    INDEX ix_security_knowledge_sources_workspace_active (workspace_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Governed workspace security knowledge sources';

CREATE TABLE IF NOT EXISTS security_knowledge_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL,
    document_version VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT NULL,
    tags_json JSON NULL,
    framework_metadata_json JSON NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from DATETIME NULL,
    effective_until DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_knowledge_source_document_version UNIQUE (source_id, document_version),
    CONSTRAINT fk_security_knowledge_documents_source FOREIGN KEY (source_id)
        REFERENCES security_knowledge_sources(id) ON DELETE CASCADE,
    INDEX ix_security_knowledge_documents_source_active (source_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned security knowledge documents';

CREATE TABLE IF NOT EXISTS remediation_suggestions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    finding_id INT NOT NULL,
    rationale TEXT NOT NULL,
    remediation_steps_json JSON NOT NULL,
    patch_diff TEXT NULL,
    citations_json JSON NULL,
    warning_codes_json JSON NULL,
    provider VARCHAR(128) NOT NULL,
    model VARCHAR(255) NULL,
    model_version VARCHAR(255) NULL,
    confidence FLOAT NULL,
    review_state ENUM('pending', 'accepted', 'rejected', 'needs_revision') NOT NULL DEFAULT 'pending',
    reviewer_id INT NULL,
    reviewed_at DATETIME NULL,
    review_comment TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_remediation_suggestion_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT fk_remediation_suggestions_finding FOREIGN KEY (finding_id)
        REFERENCES security_findings(id) ON DELETE CASCADE,
    CONSTRAINT fk_remediation_suggestions_reviewer FOREIGN KEY (reviewer_id)
        REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_remediation_suggestions_finding_created (finding_id, created_at),
    INDEX ix_remediation_suggestions_review_state (review_state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Human-reviewable remediation suggestions';

CREATE TABLE IF NOT EXISTS policy_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    updated_by VARCHAR(50) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_policy_documents_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Public-facing legal policy documents';
