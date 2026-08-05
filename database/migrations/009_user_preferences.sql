-- CyberGuard user preferences (additive only).
CREATE TABLE IF NOT EXISTS user_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    theme VARCHAR(20) NOT NULL DEFAULT 'system',
    color_preset VARCHAR(40) NOT NULL DEFAULT 'default',
    font_family VARCHAR(20) NOT NULL DEFAULT 'auto',
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_preferences_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户界面与 AI 个性化设置';
