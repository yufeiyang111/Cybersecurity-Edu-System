- =========================================
-- CyberGuard 缃戠粶瀹夊叏鏅鸿兘闂瓟鏁欏绯荤粺
-- 鏁版嵁搴撳垵濮嬪寲鑴氭湰
-- =========================================

-- 鍒涘缓鏁版嵁搴?
CREATE DATABASE IF NOT EXISTS cyberguard
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE cyberguard;

-- =========================================
-- 鐢ㄦ埛瑙掕壊琛?
-- =========================================
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '瑙掕壊鍚嶇О',
    description VARCHAR(200) COMMENT '瑙掕壊鎻忚堪',
    permissions JSON COMMENT '鏉冮檺鍒楄〃',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐢ㄦ埛瑙掕壊琛?;

-- 鍒濆鍖栬鑹?
INSERT INTO roles (name, description, permissions) VALUES
('admin', '绯荤粺绠＄悊鍛?, '["all"]'),
('teacher', '鏁欏笀鐢ㄦ埛', '["knowledge:create", "knowledge:edit", "knowledge:delete", "qa:review"]'),
('user', '鏅€氱敤鎴?, '["qa:ask", "qa:history", "favorite:manage"]'),
('guest', '娓稿', '["knowledge:view"]')
ON DUPLICATE KEY UPDATE 
    description = VALUES(description),
    permissions = VALUES(permissions);

-- =========================================
-- 鐢ㄦ埛琛?
-- =========================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '鐢ㄦ埛鍚?,
    email VARCHAR(100) UNIQUE COMMENT '閭',
    password_hash VARCHAR(255) COMMENT '瀵嗙爜鍝堝笇',
    nickname VARCHAR(50) COMMENT '鏄电О',
    avatar_url VARCHAR(255) COMMENT '澶村儚URL',
    oauth_provider VARCHAR(20) COMMENT '绗笁鏂圭櫥褰曟彁渚涘晢',
    oauth_subject VARCHAR(100) COMMENT '绗笁鏂硅处鍙峰敮涓€鏍囪瘑',
    oauth_bindings TEXT COMMENT '鍏ㄩ儴绗笁鏂圭粦瀹?JSON 鏁扮粍',
    role_id INT NOT NULL DEFAULT 3 COMMENT '瑙掕壊ID',
    is_active BOOLEAN DEFAULT TRUE COMMENT '鏄惁婵€娲?,
    last_login_at DATETIME COMMENT '鏈€鍚庣櫥褰曟椂闂?,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_oauth (oauth_provider, oauth_subject),
    FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐢ㄦ埛琛?;

-- =========================================
-- 榛樿娴嬭瘯鐢ㄦ埛锛堝瘑鐮佸潎涓?123456锛屼娇鐢?bcrypt 鍔犲瘑锛?
-- 娉ㄦ剰锛氫互涓嬪搱甯屽€煎搴旂殑瀵嗙爜鍧囦负 "123456"
-- =========================================
INSERT INTO users (username, email, password_hash, nickname, role_id) VALUES
('admin', 'admin@cyberguard.local', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '绠＄悊鍛?, 1),
('teacher', 'teacher@cyberguard.local', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '鏁欏笀', 2),
('user', 'user@cyberguard.local', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '鐢ㄦ埛', 3)
ON DUPLICATE KEY UPDATE 
    nickname = VALUES(nickname),
    role_id = VALUES(role_id);


-- =========================================
-- 鐧诲綍鏃ュ織琛?
-- =========================================
CREATE TABLE IF NOT EXISTS login_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT COMMENT '鐢ㄦ埛ID',
    ip_address VARCHAR(50) COMMENT 'IP鍦板潃',
    user_agent VARCHAR(255) COMMENT '鐢ㄦ埛浠ｇ悊',
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('success', 'failed') DEFAULT 'success' COMMENT '鐧诲綍鐘舵€?,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐧诲綍鏃ュ織琛?;

-- =========================================
-- 鐭ヨ瘑鍒嗙被琛?
-- =========================================
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '鍒嗙被鍚嶇О',
    description TEXT COMMENT '鍒嗙被鎻忚堪',
    parent_id INT DEFAULT NULL COMMENT '鐖跺垎绫籌D',
    icon VARCHAR(50) COMMENT '鍥炬爣鍚嶇О',
    sort_order INT DEFAULT 0 COMMENT '鎺掑簭',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐭ヨ瘑鍒嗙被琛?;

-- 鍒濆鍖栫煡璇嗗垎绫?
INSERT INTO categories (name, description, icon, sort_order) VALUES
('缃戠粶瀹夊叏鍩虹', '缃戠粶鍩烘湰鍘熺悊鍜屽畨鍏ㄦ蹇?, 'Connection', 1),
('Web 瀹夊叏', 'Web 搴旂敤婕忔礊涓庨槻鎶?, 'Monitor', 2),
('绯荤粺瀹夊叏', '鎿嶄綔绯荤粺瀹夊叏鍔犲浐', 'Desktop', 3),
('瀵嗙爜瀛?, '鍔犲瘑绠楁硶涓庡畨鍏ㄥ崗璁?, 'Key', 4),
('娓楅€忔祴璇?, '娓楅€忔祴璇曟柟娉曚笌宸ュ叿', 'Aim', 5),
('搴旀€ュ搷搴?, '瀹夊叏浜嬩欢鍝嶅簲鍙栬瘉', 'Warning', 6),
('鏁版嵁瀹夊叏', '鏁版嵁淇濇姢闅愮鍚堣', 'Folder', 7),
('绉诲姩瀹夊叏', '绉诲姩搴旂敤璁惧瀹夊叏', 'Mobile', 8)
ON DUPLICATE KEY UPDATE 
    description = VALUES(description),
    icon = VALUES(icon),
    sort_order = VALUES(sort_order);

-- =========================================
-- 鐭ヨ瘑鏉＄洰琛?
-- =========================================
CREATE TABLE IF NOT EXISTS knowledge_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL COMMENT '鏍囬',
    content MEDIUMTEXT NOT NULL COMMENT '鍐呭',
    summary MEDIUMTEXT COMMENT '鎽樿',
    category_id INT COMMENT '鍒嗙被ID',
    difficulty ENUM('easy', 'medium', 'hard') DEFAULT 'medium' COMMENT '闅惧害',
    source VARCHAR(200) COMMENT '鏉ユ簮',
    author_id INT COMMENT '浣滆€匢D',
    view_count INT DEFAULT 0 COMMENT '娴忚娆℃暟',
    favorite_count INT DEFAULT 0 COMMENT '鏀惰棌娆℃暟',
    status ENUM('draft', 'published', 'archived') DEFAULT 'published' COMMENT '鐘舵€?,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL,
    FULLTEXT INDEX idx_fulltext (title, content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐭ヨ瘑鏉＄洰琛?;

-- =========================================
-- 鐭ヨ瘑鏍囩鍏宠仈琛?
-- =========================================
CREATE TABLE IF NOT EXISTS knowledge_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    knowledge_id INT NOT NULL COMMENT '鐭ヨ瘑ID',
    tag_name VARCHAR(50) NOT NULL COMMENT '鏍囩鍚?,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    UNIQUE KEY unique_knowledge_tag (knowledge_id, tag_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐭ヨ瘑鏍囩鍏宠仈琛?;

-- =========================================
-- 闂瓟浼氳瘽琛?
-- =========================================
CREATE TABLE IF NOT EXISTS qa_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '鐢ㄦ埛ID',
    title VARCHAR(200) COMMENT '浼氳瘽鏍囬',
    is_archived BOOLEAN DEFAULT FALSE COMMENT '鏄惁褰掓。',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='闂瓟浼氳瘽琛?;

-- =========================================
-- 闂瓟璁板綍琛?
-- =========================================
CREATE TABLE IF NOT EXISTS qa_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT COMMENT '会话ID',
    user_id INT NOT NULL COMMENT '用户ID',
    question TEXT NOT NULL COMMENT '问题',
    answer MEDIUMTEXT COMMENT '回答内容（长回答场景使用 MEDIUMTEXT）',
    reasoning MEDIUMTEXT NULL COMMENT '模型思考过程（推理模型 reasoning_content），重新加载会话时回显',
    sources JSON COMMENT '来源信息',
    confidence FLOAT COMMENT '缃俊搴?,
    model_name VARCHAR(50) COMMENT '浣跨敤鐨勬ā鍨?,
    response_time FLOAT COMMENT '鍝嶅簲鏃堕棿(绉?',
    rag_warnings JSON NULL COMMENT 'RAG 娉ㄥ叆闃叉姢璀﹀憡锛坉ocId:flag 鍒楄〃锛?,
    feedback ENUM('good', 'neutral', 'bad') COMMENT '鐢ㄦ埛鍙嶉',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES qa_conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FULLTEXT INDEX idx_fulltext_question (question)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='闂瓟璁板綍琛?;

-- =========================================
-- 鏀惰棌琛?
-- =========================================
CREATE TABLE IF NOT EXISTS favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '鐢ㄦ埛ID',
    qa_record_id INT NOT NULL COMMENT '闂瓟璁板綍ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (qa_record_id) REFERENCES qa_records(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_qa (user_id, qa_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鏀惰棌琛?;

-- =========================================
-- 杩介棶寤鸿琛?
-- =========================================
CREATE TABLE IF NOT EXISTS suggested_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question VARCHAR(500) NOT NULL COMMENT '闂',
    suggestions JSON COMMENT '寤鸿鍒楄〃',
    category VARCHAR(100) COMMENT '鍒嗙被',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='杩介棶寤鸿琛?;

-- =========================================
-- 绯荤粺閰嶇疆琛?
-- =========================================
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '閰嶇疆閿?,
    config_value TEXT COMMENT '閰嶇疆鍊?,
    description VARCHAR(200) COMMENT '閰嶇疆鎻忚堪',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='绯荤粺閰嶇疆琛?;

-- 鍒濆鍖栫郴缁熼厤缃?
INSERT INTO system_configs (config_key, config_value, description) VALUES
('llm_api_key', '', '閫氫箟鍗冮棶 API 瀵嗛挜'),
('llm_model', 'qwen-plus', '浣跨敤鐨?LLM 妯″瀷'),
('vector_top_k', '10', '鍚戦噺妫€绱㈣繑鍥炴暟閲?),
('similarity_threshold', '0.5', '鐩镐技搴﹂槇鍊?),
('max_context_length', '4000', '鏈€澶т笂涓嬫枃闀垮害')
ON DUPLICATE KEY UPDATE 
    config_value = VALUES(config_value),
    description = VALUES(description);

-- =========================================
-- 鐭ヨ瘑鍥捐氨鍏崇郴琛?
-- =========================================
CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT '婧愯妭鐐笽D',
    target_id INT NOT NULL COMMENT '鐩爣鑺傜偣ID',
    relation_type VARCHAR(50) NOT NULL COMMENT '鍏崇郴绫诲瀷',
    weight FLOAT DEFAULT 1.0 COMMENT '鏉冮噸',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    UNIQUE KEY unique_edge (source_id, target_id, relation_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鐭ヨ瘑鍥捐氨鍏崇郴琛?;

-- =========================================
-- 鍙嶉璁板綍琛?
-- =========================================
CREATE TABLE IF NOT EXISTS feedback_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    qa_record_id INT NOT NULL COMMENT '闂瓟璁板綍ID',
    user_id INT NOT NULL COMMENT '鐢ㄦ埛ID',
    feedback_type ENUM('good', 'neutral', 'bad') COMMENT '鍙嶉绫诲瀷',
    comment TEXT COMMENT '鍙嶉璇勮',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qa_record_id) REFERENCES qa_records(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鍙嶉璁板綍琛?;

-- =========================================
-- 鍒涘缓绱㈠紩浠ヤ紭鍖栨煡璇㈡€ц兘
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
-- 浼佷笟瀹夊叏鎵弿鍩虹琛紙涓庢暟鎹簱杩佺Щ淇濇寔涓€鑷达級
-- =========================================
-- CyberGuard security scanning foundation (additive migration)
-- Apply to an existing MySQL 8+ CyberGuard database. This migration does not alter or delete legacy tables.

CREATE TABLE IF NOT EXISTS workspaces (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL,
    description TEXT NULL,
    provider_allowlist JSON NULL,
    preferred_provider VARCHAR(64) NULL,
    agent_feature_flags JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_workspaces_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='瀹夊叏宸ヤ綔鍖?;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='宸ヤ綔鍖烘垚鍛?;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='瀹夊叏鎵弿椤圭洰';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='涓嶅彲鍙橀」鐩揩鐓?;

CREATE TABLE IF NOT EXISTS scan_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    status ENUM('created', 'validating', 'snapshotting', 'scanning', 'completed', 'completed_with_warnings', 'failed', 'canceled') NOT NULL DEFAULT 'created',
    progress INT NOT NULL DEFAULT 0,
    policy_version VARCHAR(100) NULL,
    exclusion_rules JSON NULL,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='寮傛鎵弿浠诲姟';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鏍囧噯鍖栧畨鍏ㄥ彂鐜伴」';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='鑴辨晱婕忔礊璇佹嵁';

CREATE TABLE IF NOT EXISTS project_exclusion_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    pattern VARCHAR(500) NOT NULL,
    position INT NOT NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_exclusion_rules_project FOREIGN KEY (project_id) REFERENCES security_projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_exclusion_rules_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_exclusion_rules_position UNIQUE (project_id, position),
    INDEX ix_exclusion_rules_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='椤圭洰绾ф壂鎻忔帓闄よ鍒?;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='瀹夊叏鍩熷璁′簨浠?;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='蹇収渚濊禆搴撳瓨';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='婕忔礊鍏憡缂撳瓨';

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

-- =========================================
-- Agent Runtime (A1): durable runs, plan DAG, tools, events
-- =========================================
-- CyberGuard agent runtime foundation (additive only).
-- Durable AgentRun, plan DAG, step/tool executions, artifacts, checkpoints
-- and replayable AgentEvent stream.  Agent tables do NOT cascade from projects
-- so the audit trail survives project-level cleanup decisions.

CREATE TABLE IF NOT EXISTS agent_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    project_id INT NOT NULL,
    snapshot_id INT NOT NULL,
    created_by INT NULL,
    goal_text VARCHAR(4000) NOT NULL,
    mode ENUM('baseline', 'hybrid', 'deep_audit') NOT NULL DEFAULT 'baseline',
    status ENUM('created', 'queued', 'preparing', 'mapping_repository', 'planning', 'validating_plan', 'executing_tools', 'evaluating_evidence', 'replanning', 'deep_reviewing', 'awaiting_approval', 'paused', 'generating_report', 'completed', 'completed_with_warnings', 'partial', 'failed', 'canceled') NOT NULL DEFAULT 'created',
    state_version INT NOT NULL DEFAULT 0,
    plan_version INT NOT NULL DEFAULT 0,
    planner_source VARCHAR(64) NULL,
    replan_count INT NOT NULL DEFAULT 0,
    last_event_sequence INT NOT NULL DEFAULT 0,
    lease_owner VARCHAR(255) NULL,
    lease_expires_at DATETIME NULL,
    heartbeat_at DATETIME NULL,
    tool_call_count INT NOT NULL DEFAULT 0,
    llm_call_count INT NOT NULL DEFAULT 0,
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cached_input_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    max_llm_calls INT NULL,
    max_tool_calls INT NULL,
    max_total_tokens INT NULL,
    max_estimated_cost DECIMAL(12, 6) NULL,
    max_wall_clock_seconds INT NULL,
    max_deep_review_files INT NULL,
    warning_codes JSON NULL,
    error_code VARCHAR(100) NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_runs_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_agent_runs_project FOREIGN KEY (project_id) REFERENCES security_projects(id),
    CONSTRAINT fk_agent_runs_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id),
    CONSTRAINT fk_agent_runs_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_agent_runs_workspace_created (workspace_id, created_at),
    INDEX ix_agent_runs_status_lease (status, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Durable agent runs';

CREATE TABLE IF NOT EXISTS agent_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    role VARCHAR(32) NOT NULL,
    content VARCHAR(8000) NOT NULL,
    message_type VARCHAR(64) NOT NULL DEFAULT 'user_goal',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_messages_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_messages_run_created (run_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent run user messages';

CREATE TABLE IF NOT EXISTS agent_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    planner_source VARCHAR(64) NOT NULL,
    objective VARCHAR(4000) NULL,
    decision_summary VARCHAR(4000) NULL,
    hypotheses_json JSON NULL,
    completion_criteria_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plans_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_plans_run_version UNIQUE (run_id, plan_version),
    INDEX ix_agent_plans_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned agent plans';

CREATE TABLE IF NOT EXISTS agent_plan_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id INT NOT NULL,
    node_key VARCHAR(64) NOT NULL,
    node_type ENUM('inventory', 'baseline_scan', 'coverage_analysis', 'repository_mapping', 'risk_ranking', 'rag_retrieval', 'semantic_review', 'human_approval', 'remediation_generation', 'report_generation') NOT NULL,
    status ENUM('pending', 'ready', 'running', 'succeeded', 'failed', 'skipped', 'blocked', 'canceled', 'superseded') NOT NULL DEFAULT 'pending',
    title VARCHAR(500) NOT NULL,
    description VARCHAR(4000) NULL,
    tool_name VARCHAR(128) NULL,
    input_json JSON NULL,
    depends_on_json JSON NULL,
    input_artifact_refs JSON NULL,
    output_artifact_refs JSON NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plan_nodes_plan FOREIGN KEY (plan_id) REFERENCES agent_plans(id),
    CONSTRAINT uq_agent_plan_nodes_key UNIQUE (plan_id, node_key),
    INDEX ix_agent_plan_nodes_plan_status (plan_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan DAG nodes';

CREATE TABLE IF NOT EXISTS agent_plan_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id INT NOT NULL,
    from_node VARCHAR(64) NOT NULL,
    to_node VARCHAR(64) NOT NULL,
    edge_type ENUM('success', 'failure', 'condition', 'always', 'evidence_gap', 'approval_granted', 'approval_rejected', 'budget_available') NOT NULL DEFAULT 'success',
    condition_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plan_edges_plan FOREIGN KEY (plan_id) REFERENCES agent_plans(id),
    INDEX ix_agent_plan_edges_plan (plan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan DAG edges';

CREATE TABLE IF NOT EXISTS agent_step_executions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_node_id INT NOT NULL,
    run_id INT NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1,
    worker_id VARCHAR(255) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    retry_reason VARCHAR(500) NULL,
    input_artifact_refs JSON NULL,
    output_artifact_refs JSON NULL,
    warning_codes JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_steps_node FOREIGN KEY (plan_node_id) REFERENCES agent_plan_nodes(id),
    CONSTRAINT fk_agent_steps_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_steps_attempt UNIQUE (plan_node_id, attempt_number),
    INDEX ix_agent_steps_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan node execution attempts';

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_node_id INT NULL,
    step_execution_id INT NULL,
    tool_name VARCHAR(128) NOT NULL,
    tool_version VARCHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    risk_level VARCHAR(32) NOT NULL DEFAULT 'safe_read',
    idempotency_key VARCHAR(255) NOT NULL,
    input_summary VARCHAR(4000) NULL,
    output_summary VARCHAR(4000) NULL,
    artifact_refs JSON NULL,
    warning_codes JSON NULL,
    error_code VARCHAR(100) NULL,
    latency_ms INT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_tool_calls_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT fk_agent_tool_calls_node FOREIGN KEY (plan_node_id) REFERENCES agent_plan_nodes(id),
    CONSTRAINT fk_agent_tool_calls_step FOREIGN KEY (step_execution_id) REFERENCES agent_step_executions(id),
    CONSTRAINT uq_agent_tool_calls_idempotency UNIQUE (idempotency_key),
    INDEX ix_agent_tool_calls_run_status (run_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent tool invocation records';

CREATE TABLE IF NOT EXISTS agent_artifacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_node_id INT NULL,
    step_execution_id INT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    summary VARCHAR(4000) NOT NULL,
    content_hash VARCHAR(64) NULL,
    content_json JSON NULL,
    sensitive_level VARCHAR(32) NOT NULL DEFAULT 'internal',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_artifacts_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_artifacts_run_type (run_id, artifact_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent large-object artifacts';

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    state_json JSON NOT NULL,
    event_sequence INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_checkpoints_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_checkpoints_run_created (run_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent durable checkpoints';

CREATE TABLE IF NOT EXISTS agent_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    sequence INT NOT NULL,
    state_version INT NOT NULL DEFAULT 0,
    event_type VARCHAR(64) NOT NULL,
    schema_version INT NOT NULL DEFAULT 1,
    trace_id VARCHAR(64) NULL,
    occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_json JSON NULL,
    CONSTRAINT fk_agent_events_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_events_run_sequence UNIQUE (run_id, sequence),
    INDEX ix_agent_events_run_sequence (run_id, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Replayable agent events';

-- =========================================
-- Agent Runtime (A1): durable runs, plan DAG, tools, events
-- =========================================
-- CyberGuard agent runtime foundation (additive only).
-- Durable AgentRun, plan DAG, step/tool executions, artifacts, checkpoints
-- and replayable AgentEvent stream.  Agent tables do NOT cascade from projects
-- so the audit trail survives project-level cleanup decisions.

CREATE TABLE IF NOT EXISTS agent_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    workspace_id INT NOT NULL,
    project_id INT NOT NULL,
    snapshot_id INT NOT NULL,
    created_by INT NULL,
    goal_text VARCHAR(4000) NOT NULL,
    mode ENUM('baseline', 'hybrid', 'deep_audit') NOT NULL DEFAULT 'baseline',
    status ENUM('created', 'queued', 'preparing', 'mapping_repository', 'planning', 'validating_plan', 'executing_tools', 'evaluating_evidence', 'replanning', 'deep_reviewing', 'awaiting_approval', 'paused', 'generating_report', 'completed', 'completed_with_warnings', 'partial', 'failed', 'canceled') NOT NULL DEFAULT 'created',
    state_version INT NOT NULL DEFAULT 0,
    plan_version INT NOT NULL DEFAULT 0,
    planner_source VARCHAR(64) NULL,
    replan_count INT NOT NULL DEFAULT 0,
    last_event_sequence INT NOT NULL DEFAULT 0,
    lease_owner VARCHAR(255) NULL,
    lease_expires_at DATETIME NULL,
    heartbeat_at DATETIME NULL,
    tool_call_count INT NOT NULL DEFAULT 0,
    llm_call_count INT NOT NULL DEFAULT 0,
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cached_input_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    max_llm_calls INT NULL,
    max_tool_calls INT NULL,
    max_total_tokens INT NULL,
    max_estimated_cost DECIMAL(12, 6) NULL,
    max_wall_clock_seconds INT NULL,
    max_deep_review_files INT NULL,
    warning_codes JSON NULL,
    error_code VARCHAR(100) NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_runs_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_agent_runs_project FOREIGN KEY (project_id) REFERENCES security_projects(id),
    CONSTRAINT fk_agent_runs_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id),
    CONSTRAINT fk_agent_runs_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_agent_runs_workspace_created (workspace_id, created_at),
    INDEX ix_agent_runs_status_lease (status, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Durable agent runs';

CREATE TABLE IF NOT EXISTS agent_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    role VARCHAR(32) NOT NULL,
    content VARCHAR(8000) NOT NULL,
    message_type VARCHAR(64) NOT NULL DEFAULT 'user_goal',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_messages_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_messages_run_created (run_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent run user messages';

CREATE TABLE IF NOT EXISTS agent_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    planner_source VARCHAR(64) NOT NULL,
    objective VARCHAR(4000) NULL,
    decision_summary VARCHAR(4000) NULL,
    hypotheses_json JSON NULL,
    completion_criteria_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plans_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_plans_run_version UNIQUE (run_id, plan_version),
    INDEX ix_agent_plans_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned agent plans';

CREATE TABLE IF NOT EXISTS agent_plan_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id INT NOT NULL,
    node_key VARCHAR(64) NOT NULL,
    node_type ENUM('inventory', 'baseline_scan', 'coverage_analysis', 'repository_mapping', 'risk_ranking', 'rag_retrieval', 'semantic_review', 'human_approval', 'remediation_generation', 'report_generation') NOT NULL,
    status ENUM('pending', 'ready', 'running', 'succeeded', 'failed', 'skipped', 'blocked', 'canceled', 'superseded') NOT NULL DEFAULT 'pending',
    title VARCHAR(500) NOT NULL,
    description VARCHAR(4000) NULL,
    tool_name VARCHAR(128) NULL,
    input_json JSON NULL,
    depends_on_json JSON NULL,
    input_artifact_refs JSON NULL,
    output_artifact_refs JSON NULL,
    retry_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plan_nodes_plan FOREIGN KEY (plan_id) REFERENCES agent_plans(id),
    CONSTRAINT uq_agent_plan_nodes_key UNIQUE (plan_id, node_key),
    INDEX ix_agent_plan_nodes_plan_status (plan_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan DAG nodes';

CREATE TABLE IF NOT EXISTS agent_plan_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id INT NOT NULL,
    from_node VARCHAR(64) NOT NULL,
    to_node VARCHAR(64) NOT NULL,
    edge_type ENUM('success', 'failure', 'condition', 'always', 'evidence_gap', 'approval_granted', 'approval_rejected', 'budget_available') NOT NULL DEFAULT 'success',
    condition_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_plan_edges_plan FOREIGN KEY (plan_id) REFERENCES agent_plans(id),
    INDEX ix_agent_plan_edges_plan (plan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan DAG edges';

CREATE TABLE IF NOT EXISTS agent_step_executions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_node_id INT NOT NULL,
    run_id INT NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1,
    worker_id VARCHAR(255) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    retry_reason VARCHAR(500) NULL,
    input_artifact_refs JSON NULL,
    output_artifact_refs JSON NULL,
    warning_codes JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_steps_node FOREIGN KEY (plan_node_id) REFERENCES agent_plan_nodes(id),
    CONSTRAINT fk_agent_steps_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_steps_attempt UNIQUE (plan_node_id, attempt_number),
    INDEX ix_agent_steps_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent plan node execution attempts';

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_node_id INT NULL,
    step_execution_id INT NULL,
    tool_name VARCHAR(128) NOT NULL,
    tool_version VARCHAR(64) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    risk_level VARCHAR(32) NOT NULL DEFAULT 'safe_read',
    idempotency_key VARCHAR(255) NOT NULL,
    input_summary VARCHAR(4000) NULL,
    output_summary VARCHAR(4000) NULL,
    artifact_refs JSON NULL,
    warning_codes JSON NULL,
    error_code VARCHAR(100) NULL,
    latency_ms INT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_tool_calls_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT fk_agent_tool_calls_node FOREIGN KEY (plan_node_id) REFERENCES agent_plan_nodes(id),
    CONSTRAINT fk_agent_tool_calls_step FOREIGN KEY (step_execution_id) REFERENCES agent_step_executions(id),
    CONSTRAINT uq_agent_tool_calls_idempotency UNIQUE (idempotency_key),
    INDEX ix_agent_tool_calls_run_status (run_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent tool invocation records';

CREATE TABLE IF NOT EXISTS agent_artifacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_node_id INT NULL,
    step_execution_id INT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    summary VARCHAR(4000) NOT NULL,
    content_hash VARCHAR(64) NULL,
    content_json JSON NULL,
    sensitive_level VARCHAR(32) NOT NULL DEFAULT 'internal',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_artifacts_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_artifacts_run_type (run_id, artifact_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent large-object artifacts';

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    state_json JSON NOT NULL,
    event_sequence INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_checkpoints_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    INDEX ix_agent_checkpoints_run_created (run_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent durable checkpoints';

CREATE TABLE IF NOT EXISTS agent_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    sequence INT NOT NULL,
    state_version INT NOT NULL DEFAULT 0,
    event_type VARCHAR(64) NOT NULL,
    schema_version INT NOT NULL DEFAULT 1,
    trace_id VARCHAR(64) NULL,
    occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_json JSON NULL,
    CONSTRAINT fk_agent_events_run FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    CONSTRAINT uq_agent_events_run_sequence UNIQUE (run_id, sequence),
    INDEX ix_agent_events_run_sequence (run_id, sequence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Replayable agent events';


-- =========================================
-- Scan Coverage (A2): snapshot file catalog + scan receipts
-- =========================================
-- CyberGuard scan coverage foundation (additive only).
-- Immutable per-snapshot file catalog plus idempotent per-scan receipts so the
-- agent and the UI can answer "what was scanned" instead of only seeing files
-- that produced findings.

CREATE TABLE IF NOT EXISTS project_snapshot_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    extension VARCHAR(64) NULL,
    is_text TINYINT(1) NOT NULL DEFAULT 0,
    detected_language VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_snapshot_files_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE,
    CONSTRAINT uq_snapshot_files_path UNIQUE (snapshot_id, file_path),
    INDEX ix_snapshot_files_snapshot_text (snapshot_id, is_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Immutable snapshot file catalog';

CREATE TABLE IF NOT EXISTS scan_file_receipts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    snapshot_id INT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    scanner_name VARCHAR(128) NOT NULL,
    coverage_kind ENUM('accounted', 'baseline_scanned', 'specialized_sast', 'generic_only', 'scanned_no_finding', 'scanned_with_findings', 'excluded', 'skipped', 'failed') NOT NULL DEFAULT 'accounted',
    file_size BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scan_receipts_task FOREIGN KEY (task_id) REFERENCES scan_tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_scan_receipts_snapshot FOREIGN KEY (snapshot_id) REFERENCES project_snapshots(id) ON DELETE CASCADE,
    CONSTRAINT uq_scan_receipts_scope UNIQUE (task_id, file_path, scanner_name, coverage_kind),
    INDEX ix_scan_receipts_task_status (task_id, coverage_kind),
    INDEX ix_scan_receipts_snapshot (snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Idempotent per-file scan receipts';

-- =========================================
-- Agent Conversations (2A): long-lived sessions, turns, idempotent messages
-- =========================================
-- =========================================
-- Agent Conversations (2A): long-lived sessions, turns, idempotent messages
-- =========================================
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

-- =========================================
-- User-managed LLM providers and safe call metadata
-- =========================================
CREATE TABLE IF NOT EXISTS llm_provider_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    provider_type VARCHAR(32) NOT NULL DEFAULT 'openai_compatible',
    base_url VARCHAR(500) NOT NULL,
    model VARCHAR(200) NOT NULL,
    api_key_ciphertext TEXT NOT NULL,
    api_key_hint VARCHAR(64) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    max_tokens INT NULL COMMENT '自定义最大输出 tokens，NULL 使用默认 2048',
    last_check_status VARCHAR(32),
    last_checked_at DATETIME NULL,
    last_latency_ms INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_llm_provider_configs_user_name UNIQUE (user_id, name),
    CONSTRAINT fk_llm_provider_configs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_llm_provider_configs_user_default (user_id, is_default),
    INDEX ix_llm_provider_configs_user_enabled (user_id, is_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User-managed OpenAI-compatible LLM providers';

-- =========================================
-- Per-user chat preferences（009 + 019 + 023 + 034 同步）
-- =========================================
CREATE TABLE IF NOT EXISTS user_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    theme VARCHAR(20) NOT NULL DEFAULT 'system',
    color_preset VARCHAR(40) NOT NULL DEFAULT 'default',
    font_family VARCHAR(20) NOT NULL DEFAULT 'auto',
    font_size VARCHAR(20) NOT NULL DEFAULT 'medium',
    border_radius VARCHAR(20) NOT NULL DEFAULT 'auto',
    content_density VARCHAR(20) NOT NULL DEFAULT 'standard',
    content_width VARCHAR(20) NOT NULL DEFAULT 'standard',
    language VARCHAR(20) NOT NULL DEFAULT 'zh-CN',
    about_user VARCHAR(1000) NOT NULL DEFAULT '',
    response_preferences VARCHAR(2000) NOT NULL DEFAULT '',
    custom_prompt VARCHAR(4000) NOT NULL DEFAULT '',
    response_style VARCHAR(20) NOT NULL DEFAULT 'professional',
    show_citations BOOLEAN NOT NULL DEFAULT TRUE,
    show_security_warnings BOOLEAN NOT NULL DEFAULT TRUE,
    persistent_memory_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    qa_max_tokens INT NULL COMMENT 'QA 回答最大输出 tokens，NULL 使用引擎默认 16384',
    analytics_time_range VARCHAR(20) NOT NULL DEFAULT '1d' COMMENT '模型分析默认时间范围：1h/6h/1d/7d/30d',
    analytics_time_granularity VARCHAR(20) NOT NULL DEFAULT 'hour' COMMENT '模型分析默认时间粒度：hour/day',
    analytics_chart_type VARCHAR(20) NOT NULL DEFAULT 'bar' COMMENT '模型分析默认消耗分布图：bar/area',
    analytics_model_chart VARCHAR(20) NOT NULL DEFAULT 'trend' COMMENT '模型分析默认模型调用图：trend/distribution/ranking',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_preferences_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户界面与 AI 个性化设置';

CREATE TABLE IF NOT EXISTS llm_call_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    provider_config_id INT NULL,
    provider_name VARCHAR(128) NOT NULL,
    model VARCHAR(200),
    operation VARCHAR(64) NOT NULL DEFAULT 'unknown',
    status VARCHAR(32) NOT NULL,
    warning_code VARCHAR(100),
    request_id VARCHAR(64),
    streaming BOOLEAN NOT NULL DEFAULT FALSE,
    input_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cached_input_tokens INT NOT NULL DEFAULT 0,
    cache_status VARCHAR(16) NULL,
    cache_write_input_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    cost_amount DECIMAL(12, 6) NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    latency_ms INT NULL,
    first_token_latency_ms INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_llm_call_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_llm_call_logs_provider FOREIGN KEY (provider_config_id) REFERENCES llm_provider_configs(id) ON DELETE SET NULL,
    INDEX ix_llm_call_logs_user_created (user_id, created_at),
    INDEX ix_llm_call_logs_user_model_created (user_id, model, created_at),
    INDEX ix_llm_call_logs_user_provider_created (user_id, provider_config_id, created_at),
    INDEX ix_llm_call_logs_user_status_created (user_id, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Non-sensitive LLM call metadata';

CREATE TABLE IF NOT EXISTS user_memories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content VARCHAR(2000) NOT NULL,
    category VARCHAR(32) NOT NULL DEFAULT 'fact',
    source_conversation_id INT NULL,
    source_record_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_reinforced_at DATETIME NULL COMMENT '最近被检索引用时间（强化）',
    expires_at DATETIME NULL COMMENT '过期时间，NULL 表示永不过期',
    CONSTRAINT fk_user_memories_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_memories_record FOREIGN KEY (source_record_id) REFERENCES qa_records(id) ON DELETE SET NULL,
    INDEX ix_user_memories_user_created (user_id, created_at),
    INDEX ix_user_memories_user_category (user_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User-scoped persistent memories extracted from QA';

CREATE TABLE IF NOT EXISTS memory_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    memory_id INT NOT NULL,
    user_id INT NOT NULL,
    rating TINYINT NOT NULL COMMENT '1=有用 0=没用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_feedback_memory (memory_id),
    INDEX ix_memory_feedback_user (user_id),
    CONSTRAINT fk_memory_feedback_memory FOREIGN KEY (memory_id)
        REFERENCES user_memories (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_feedback_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆反馈';

CREATE TABLE IF NOT EXISTS memory_entities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    memory_id INT NULL,
    name VARCHAR(128) NOT NULL,
    entity_type VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT 'person/org/tech/other',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_entities_user_name (user_id, name),
    INDEX ix_memory_entities_memory (memory_id),
    CONSTRAINT fk_memory_entities_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_entities_memory FOREIGN KEY (memory_id)
        REFERENCES user_memories (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆实体';

CREATE TABLE IF NOT EXISTS memory_entity_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    source_entity_id INT NOT NULL,
    target_entity_id INT NOT NULL,
    relation VARCHAR(64) NOT NULL DEFAULT 'related',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_entity_links_source (source_entity_id),
    INDEX ix_memory_entity_links_target (target_entity_id),
    CONSTRAINT fk_memory_entity_links_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_entity_links_source FOREIGN KEY (source_entity_id)
        REFERENCES memory_entities (id) ON DELETE CASCADE,
    CONSTRAINT fk_memory_entity_links_target FOREIGN KEY (target_entity_id)
        REFERENCES memory_entities (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆实体关系';

CREATE TABLE IF NOT EXISTS memory_dream_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(32) NOT NULL COMMENT 'synthesize/supersede/merge',
    memory_ids VARCHAR(512) NULL COMMENT '被处理记忆 id 列表（逗号分隔）',
    detail VARCHAR(2000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_memory_dream_audit_user (user_id, created_at),
    CONSTRAINT fk_memory_dream_audit_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Dream 记忆整合审计';
-- CyberGuard agent-run LLM invocations and versioned price catalog (additive only).
CREATE TABLE IF NOT EXISTS llm_invocations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    step_execution_id INT NULL,
    workspace_id INT NOT NULL,
    user_id INT NULL,
    provider_config_id INT NULL,
    provider_name VARCHAR(128) NOT NULL,
    model VARCHAR(200),
    model_version VARCHAR(64),
    operation VARCHAR(64) NOT NULL DEFAULT 'unknown',
    prompt_template_version VARCHAR(64),
    input_digest VARCHAR(64),
    output_digest VARCHAR(64),
    status VARCHAR(32) NOT NULL,
    warning_code VARCHAR(100),
    latency_ms INT NULL,
    first_token_latency_ms INT NULL,
    input_tokens INT NOT NULL DEFAULT 0,
    cached_input_tokens INT NOT NULL DEFAULT 0,
    cache_creation_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    usage_source VARCHAR(24) NOT NULL DEFAULT 'unknown',
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    input_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    cached_input_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    output_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    reasoning_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0,
    pricing_version VARCHAR(64),
    provider_cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    application_cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_llm_invocations_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_llm_invocations_step FOREIGN KEY (step_execution_id) REFERENCES agent_step_executions(id) ON DELETE SET NULL,
    CONSTRAINT fk_llm_invocations_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_llm_invocations_provider FOREIGN KEY (provider_config_id) REFERENCES llm_provider_configs(id) ON DELETE SET NULL,
    INDEX ix_llm_invocations_run_created (run_id, created_at),
    INDEX ix_llm_invocations_workspace_created (workspace_id, created_at),
    INDEX ix_llm_invocations_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Per-invocation agent LLM usage and cost audit';

CREATE TABLE IF NOT EXISTS llm_price_catalog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider_name VARCHAR(128) NOT NULL,
    model VARCHAR(200) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    effective_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    input_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    cached_input_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    output_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    reasoning_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
    pricing_version VARCHAR(64) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'builtin',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_llm_price_catalog_entry UNIQUE (provider_name, model, currency, pricing_version),
    INDEX ix_llm_price_catalog_model (model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Versioned per-million-token price snapshots';

-- Built-in estimated prices (USD per million tokens); real prices are snapshotted by
-- future admin flows. Costs computed from this catalog are flagged usage_source=estimated.
INSERT IGNORE INTO llm_price_catalog
    (provider_name, model, currency, input_price_per_million, cached_input_price_per_million, output_price_per_million, reasoning_price_per_million, pricing_version, source)
VALUES
    ('deepseek-chat', 'deepseek-chat', 'USD', 0.270000, 0.027000, 1.100000, 0.000000, 'builtin-v1', 'builtin'),
    ('deepseek-reasoner', 'deepseek-reasoner', 'USD', 0.550000, 0.055000, 2.190000, 0.000000, 'builtin-v1', 'builtin'),
    ('gpt-4o-mini', 'gpt-4o-mini', 'USD', 0.150000, 0.075000, 0.600000, 0.000000, 'builtin-v1', 'builtin'),
    ('gpt-4o', 'gpt-4o', 'USD', 2.500000, 1.250000, 10.000000, 0.000000, 'builtin-v1', 'builtin'),
    ('glm-4-plus', 'glm-4-plus', 'USD', 0.700000, 0.070000, 1.400000, 0.000000, 'builtin-v1', 'builtin'),
    ('minimax', 'MiniMax-Text-01', 'USD', 0.200000, 0.020000, 1.100000, 0.000000, 'builtin-v1', 'builtin');


-- RAG retrieval logging + offline evaluation set (migration 018)
CREATE TABLE IF NOT EXISTS qa_retrieval_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NOT NULL,
    query TEXT NOT NULL,
    conversation_id INT UNSIGNED NULL,
    record_id BIGINT UNSIGNED NULL,
    engine_version VARCHAR(64) NOT NULL DEFAULT 'enhanced',
    model_name VARCHAR(64) NULL,
    retrieved_docs JSON NULL COMMENT '妫€绱㈠懡涓殑鏂囨。(鍚玠oc_id/title/similarity/琛屽彿)',
    sources JSON NULL COMMENT '鏈€缁堝紩鐢ㄦ潵婧?,
    retrieval_ms INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_retrieval_logs_user (user_id, created_at),
    KEY idx_retrieval_logs_record (record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS rag_eval_cases (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    query VARCHAR(500) NOT NULL,
    expected_doc_ids JSON NOT NULL COMMENT '鏈熸湜鍛戒腑鐨勭煡璇嗘潯鐩?id 鍒楄〃',
    expected_answer TEXT NULL COMMENT '鏈熸湜绛旀瑕佺偣锛堢敤浜庣瓟妗堢浉鍏虫€ц瘎浼帮級',
    category VARCHAR(64) NULL,
    notes VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_eval_cases_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS memory_eval_cases (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    query TEXT NOT NULL COMMENT '评测问题',
    expected_content TEXT NOT NULL COMMENT '期望命中的记忆内容',
    category VARCHAR(32) NOT NULL DEFAULT 'fact' COMMENT '记忆分类',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_memory_eval_cases_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO memory_eval_cases (query, expected_content, category) VALUES
('用户关注哪个安全方向？', '用户负责公司安全运营，重点关注 Web 安全', 'fact'),
('用户平时用什么系统工作？', '用户使用 Linux 和 Windows 双环境进行安全工作', 'fact'),
('用户喜欢什么样的回答风格？', '用户偏好简洁直接的回答，不要长篇大论', 'preference'),
('用户对回答有什么格式要求？', '用户希望回答包含编号步骤和结论摘要', 'preference'),
('用户决定用什么数据库？', '项目数据库决定：使用 PostgreSQL 作为主库', 'decision'),
('用户今年的目标是什么？', '用户目标是三个月内通过 OSCP 认证', 'goal'),
('用户负责什么工作？', '用户是安全运营工程师，负责漏洞排查与应急响应', 'fact'),
('用户团队的规模？', '用户所在安全团队共 5 人，包含 2 名开发', 'fact'),
('用户偏好的会议形式？', '用户偏好 30 分钟以内的短会，会议要有明确结论', 'preference'),
('用户上一次的架构选择？', '决定采用微服务架构拆分安全网关模块', 'decision'),
('用户想学习什么技能？', '用户计划下半年学习云原生安全与容器安全', 'goal'),
('用户的客户类型？', '用户所在公司主要服务金融行业的客户', 'fact')
ON DUPLICATE KEY UPDATE query = VALUES(query);

-- =========================================
-- Help center: tree-shaped categories + markdown documents (migration 021)
-- =========================================
CREATE TABLE IF NOT EXISTS help_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(64) NOT NULL,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(255) NULL,
    parent_id INT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_help_categories_slug UNIQUE (slug),
    CONSTRAINT fk_help_categories_parent FOREIGN KEY (parent_id) REFERENCES help_categories (id) ON DELETE RESTRICT,
    KEY idx_help_categories_parent (parent_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帮助中心分类（支持 parent_id 自引用，构树形）';

CREATE TABLE IF NOT EXISTS help_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(96) NOT NULL,
    category_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary VARCHAR(500) NULL,
    content MEDIUMTEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    version INT NOT NULL DEFAULT 1,
    updated_by VARCHAR(50) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_help_documents_slug UNIQUE (slug),
    CONSTRAINT fk_help_documents_category FOREIGN KEY (category_id) REFERENCES help_categories (id) ON DELETE RESTRICT,
    KEY idx_help_documents_category (category_id, sort_order),
    KEY idx_help_documents_active (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帮助中心文档（Markdown 正文，管理员编辑）';
-- =========================================
-- Project Security Graph (migration 027)
-- =========================================
CREATE TABLE IF NOT EXISTS project_security_graph_nodes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    mapper_version VARCHAR(64) NOT NULL COMMENT 'buildermap version, idempotent cache isolation',
    node_key VARCHAR(512) NOT NULL COMMENT 'unique key within snapshot, e.g. py:file:app/routes/qa.py',
    node_type VARCHAR(32) NOT NULL COMMENT 'route/middleware/service/repository/model/function/dependency/external_call/file',
    label VARCHAR(512) NOT NULL,
    file_path VARCHAR(512) NULL,
    start_line INT NULL,
    end_line INT NULL,
    language VARCHAR(32) NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_graph_nodes_scope UNIQUE (snapshot_id, mapper_version, node_key),
    INDEX ix_graph_nodes_snapshot_type (snapshot_id, mapper_version, node_type),
    INDEX ix_graph_nodes_snapshot_file (snapshot_id, file_path),
    CONSTRAINT fk_graph_nodes_snapshot FOREIGN KEY (snapshot_id)
        REFERENCES project_snapshots (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='project security graph nodes';

CREATE TABLE IF NOT EXISTS project_security_graph_edges (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    mapper_version VARCHAR(64) NOT NULL,
    source_node_id BIGINT NOT NULL,
    target_node_id BIGINT NOT NULL,
    edge_type VARCHAR(32) NOT NULL COMMENT 'calls/imports/inherits/decorated_by/route_handles/contains/has_dependency/calls_into',
    extractor VARCHAR(64) NOT NULL COMMENT 'python_ast/js_heuristic/java_partial/go_partial',
    confidence VARCHAR(16) NOT NULL COMMENT 'exact/heuristic/partial',
    quality INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_graph_edges_snapshot_source (snapshot_id, source_node_id),
    INDEX ix_graph_edges_snapshot_target (snapshot_id, target_node_id),
    CONSTRAINT fk_graph_edges_snapshot FOREIGN KEY (snapshot_id)
        REFERENCES project_snapshots (id) ON DELETE CASCADE,
    CONSTRAINT fk_graph_edges_source FOREIGN KEY (source_node_id)
        REFERENCES project_security_graph_nodes (id) ON DELETE CASCADE,
    CONSTRAINT fk_graph_edges_target FOREIGN KEY (target_node_id)
        REFERENCES project_security_graph_nodes (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='project security graph edges';
-- =========================================
-- 知识图谱社区摘要缓存（GraphRAG 风格）
-- =========================================
CREATE TABLE IF NOT EXISTS kg_community_summaries (
    community_id VARCHAR(64) NOT NULL PRIMARY KEY COMMENT '社区 partition id',
    graph_signature VARCHAR(255) NOT NULL COMMENT '生成时的图谱签名（节点数:边数），变化后摘要失效',
    algorithm VARCHAR(16) NOT NULL COMMENT '社区检测算法 leiden/louvain',
    title VARCHAR(512) NOT NULL COMMENT '社区主题标题',
    summary MEDIUMTEXT NOT NULL COMMENT '社区总结正文',
    summary_json JSON NOT NULL COMMENT '完整结构化摘要（关键主题/代表实体/关键关系/安全启示/防御建议）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_kg_comm_sum_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识图谱社区摘要缓存';

CREATE TABLE IF NOT EXISTS agent_decision_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    plan_version INT NOT NULL,
    supersedes_version INT NULL,
    reason_code VARCHAR(64) NOT NULL,
    decision_type VARCHAR(32) NOT NULL,
    detail_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_decision_records_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    INDEX ix_agent_decision_records_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A5 agent replan decision records';

CREATE TABLE IF NOT EXISTS agent_observations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    status ENUM('unverified', 'confirmed', 'rejected', 'needs_more_evidence') NOT NULL DEFAULT 'unverified',
    cwe_id VARCHAR(32) NULL,
    confidence VARCHAR(16) NOT NULL DEFAULT 'low',
    summary TEXT NOT NULL,
    detail_json JSON NULL,
    proof_gaps_json JSON NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'deep_review',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_observations_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    INDEX ix_agent_observations_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A6 Agent deep review observations';

CREATE TABLE IF NOT EXISTS agent_observation_locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    observation_id INT NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    start_line INT NOT NULL,
    end_line INT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'evidence',
    CONSTRAINT fk_agent_obs_locations_obs FOREIGN KEY (observation_id) REFERENCES agent_observations(id) ON DELETE CASCADE,
    INDEX ix_agent_obs_locations_obs (observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A6 observation locations';

CREATE TABLE IF NOT EXISTS agent_observation_citations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    observation_id INT NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'rag',
    document_id VARCHAR(255) NULL,
    document_title VARCHAR(500) NULL,
    trust_score FLOAT NULL,
    injection_flags JSON NULL,
    content_digest VARCHAR(64) NOT NULL,
    quote_preview VARCHAR(2000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_obs_citations_obs FOREIGN KEY (observation_id) REFERENCES agent_observations(id) ON DELETE CASCADE,
    INDEX ix_agent_obs_citations_obs (observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A6 observation citations';

CREATE TABLE IF NOT EXISTS agent_approvals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    workspace_id INT NOT NULL,
    operation_type VARCHAR(64) NOT NULL,
    risk_level VARCHAR(16) NOT NULL DEFAULT 'medium',
    reason VARCHAR(1000) NOT NULL,
    affected_scope_json JSON NULL,
    operation_digest VARCHAR(64) NOT NULL,
    proposed_json JSON NULL,
    requested_by INT NULL,
    status ENUM('pending', 'approved', 'rejected', 'expired', 'canceled') NOT NULL DEFAULT 'pending',
    decision_comment VARCHAR(1000) NULL,
    resolver_id INT NULL,
    expires_at DATETIME NULL,
    resolved_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_agent_approvals_digest (operation_digest),
    CONSTRAINT fk_agent_approvals_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    INDEX ix_agent_approvals_run (run_id),
    INDEX ix_agent_approvals_workspace (workspace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A7 agent approvals';

-- ============================================================
-- Agent Loop v2 foundation (T02, additive only; mirrors 035_agent_loop_items.sql)
-- ============================================================

CREATE TABLE IF NOT EXISTS agent_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL,
    conversation_id INT NULL,
    turn_id INT NULL,
    run_id INT NOT NULL,
    iteration INT NOT NULL DEFAULT 0,
    item_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'started',
    parent_item_id VARCHAR(64) NULL,
    content_redacted MEDIUMTEXT NULL,
    summary_json JSON NULL,
    sensitive_level VARCHAR(32) NOT NULL DEFAULT 'internal',
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_agent_items_public_id UNIQUE (public_id),
    CONSTRAINT fk_agent_items_conversation FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id),
    CONSTRAINT fk_agent_items_turn FOREIGN KEY (turn_id) REFERENCES agent_turns(id),
    CONSTRAINT fk_agent_items_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    INDEX ix_agent_items_run_created (run_id, created_at),
    INDEX ix_agent_items_run_type (run_id, item_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Unified agent timeline items';

CREATE TABLE IF NOT EXISTS agent_control_inputs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL,
    conversation_id INT NULL,
    turn_id INT NULL,
    run_id INT NOT NULL,
    input_type VARCHAR(32) NOT NULL,
    client_request_id VARCHAR(64) NOT NULL,
    payload_json JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    applied_iteration INT NULL,
    created_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_at DATETIME NULL,
    CONSTRAINT uq_agent_control_inputs_run_request UNIQUE (run_id, client_request_id),
    CONSTRAINT fk_agent_control_inputs_conversation FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id),
    CONSTRAINT fk_agent_control_inputs_turn FOREIGN KEY (turn_id) REFERENCES agent_turns(id),
    CONSTRAINT fk_agent_control_inputs_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_agent_control_inputs_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_agent_control_inputs_run_status (run_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Ordered agent control inputs';

CREATE TABLE IF NOT EXISTS agent_conversation_summaries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    summary_version INT NOT NULL,
    source_sequence_from INT NOT NULL,
    source_sequence_to INT NOT NULL,
    summary_json JSON NOT NULL,
    content_digest VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_agent_conversation_summaries_version UNIQUE (conversation_id, summary_version),
    CONSTRAINT fk_agent_conversation_summaries_conv FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id) ON DELETE CASCADE,
    INDEX ix_agent_conversation_summaries_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Structured conversation compression summaries';

ALTER TABLE agent_events ADD COLUMN conversation_id INT NULL;
ALTER TABLE agent_events ADD COLUMN turn_id INT NULL;
ALTER TABLE agent_events ADD COLUMN iteration INT NOT NULL DEFAULT 0;
ALTER TABLE agent_events ADD COLUMN item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_events ADD COLUMN parent_item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_events ADD COLUMN dedupe_key VARCHAR(255) NULL;

ALTER TABLE agent_runs ADD COLUMN iteration_count INT NOT NULL DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN max_iterations INT NULL;
ALTER TABLE agent_runs ADD COLUMN current_item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_runs ADD COLUMN policy_snapshot_json JSON NULL;
ALTER TABLE agent_runs ADD COLUMN tool_catalog_digest VARCHAR(64) NULL;
ALTER TABLE agent_runs ADD COLUMN context_watermark INT NOT NULL DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN last_checkpoint_id INT NULL;

ALTER TABLE agent_tool_calls ADD COLUMN provider_call_id VARCHAR(128) NULL;
ALTER TABLE agent_tool_calls ADD COLUMN logical_call_key VARCHAR(255) NULL;
ALTER TABLE agent_tool_calls ADD COLUMN attempt_number INT NOT NULL DEFAULT 1;
ALTER TABLE agent_tool_calls ADD COLUMN arguments_digest VARCHAR(64) NULL;
ALTER TABLE agent_tool_calls ADD COLUMN result_schema_version INT NULL;
ALTER TABLE agent_tool_calls ADD COLUMN retryable TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE agent_tool_calls ADD COLUMN deadline_at DATETIME NULL;
ALTER TABLE agent_tool_calls ADD COLUMN item_public_id VARCHAR(64) NULL;

ALTER TABLE agent_checkpoints ADD COLUMN iteration INT NOT NULL DEFAULT 0;
ALTER TABLE agent_checkpoints ADD COLUMN context_watermark INT NOT NULL DEFAULT 0;
ALTER TABLE agent_checkpoints ADD COLUMN current_item_public_id VARCHAR(64) NULL;
ALTER TABLE agent_checkpoints ADD COLUMN lease_owner VARCHAR(255) NULL;
ALTER TABLE agent_checkpoints ADD COLUMN checkpoint_digest VARCHAR(64) NULL;
