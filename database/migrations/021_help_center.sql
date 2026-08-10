-- 帮助中心：树形分类 + 文档（additive only）。
-- 公共阅读入口挂 /api/help/*；管理端 CRUD 挂 /api/help/admin/*。

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