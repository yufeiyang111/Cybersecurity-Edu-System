-- A4 项目安全有向图（additive only）：Project Security Graph 节点与边。
-- 1) project_security_graph_nodes：文件/类/函数/路由/依赖等符号节点；
-- 2) project_security_graph_edges：调用、导入、继承、路由处理等关系边（含 confidence/extractor）。

CREATE TABLE IF NOT EXISTS project_security_graph_nodes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id INT NOT NULL,
    mapper_version VARCHAR(64) NOT NULL COMMENT '建图器版本，用于幂等缓存隔离',
    node_key VARCHAR(512) NOT NULL COMMENT '快照内唯一键，如 py:file:app/routes/qa.py',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目安全图节点';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目安全图边';
