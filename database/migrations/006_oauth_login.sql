-- CyberGuard OAuth third-party login support (additive only).
-- Allows Google / GitHub login: email & password_hash become optional,
-- and each user may carry a unique (provider, subject) pair.

ALTER TABLE users MODIFY COLUMN email VARCHAR(100) NULL COMMENT '邮箱';
ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) NULL COMMENT '密码哈希';
ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(20) NULL COMMENT '第三方登录提供商' AFTER avatar_url;
ALTER TABLE users ADD COLUMN oauth_subject VARCHAR(100) NULL COMMENT '第三方账号唯一标识' AFTER oauth_provider;
ALTER TABLE users ADD UNIQUE INDEX uq_users_oauth (oauth_provider, oauth_subject);
