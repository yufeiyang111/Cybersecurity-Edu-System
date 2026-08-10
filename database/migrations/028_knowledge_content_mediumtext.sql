-- 知识库条目内容字段升级为 MEDIUMTEXT（16MB），支持导入大型安全文档（additive only）。
-- 背景：HackTricks 等安全知识库单篇文档可达 100KB+，TEXT 上限 64KB 会导致导入失败（Data too long for column 'content'）。

ALTER TABLE knowledge_items
    MODIFY COLUMN content MEDIUMTEXT NOT NULL COMMENT '内容（长文档场景使用 MEDIUMTEXT）';

ALTER TABLE knowledge_items
    MODIFY COLUMN summary MEDIUMTEXT NULL COMMENT '摘要（长摘要场景使用 MEDIUMTEXT）';
