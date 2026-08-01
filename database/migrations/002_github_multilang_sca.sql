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
