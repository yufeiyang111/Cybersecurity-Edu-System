-- GraphRAG 风格社区摘要缓存（additive only）：知识图谱社区检测结果的 LLM 生成摘要。
-- community_id 为社区检测的 partition id；graph_signature 记录生成时的图谱签名
-- （节点数:边数），图谱变化后签名不匹配即视为失效，重新生成时覆盖同主键行。
-- 表内最多 62 行（社区数），摘要体积小，直接按 community_id upsert。

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
