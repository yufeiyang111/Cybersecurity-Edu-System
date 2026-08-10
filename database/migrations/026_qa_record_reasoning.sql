-- QA 记录保存模型思考过程（reasoning），刷新页面后可回显（additive only）。
-- 文本字段统一 MEDIUMTEXT（16MB）：推理模型 reasoning 与长回答内容较大。

ALTER TABLE qa_records
    ADD COLUMN reasoning MEDIUMTEXT NULL COMMENT '模型思考过程（推理模型 reasoning_content），重新加载会话时回显';

ALTER TABLE qa_records
    MODIFY COLUMN answer MEDIUMTEXT NULL COMMENT '回答内容（长回答场景使用 MEDIUMTEXT）';
