-- =========================================
-- 039 问答记录附件持久化
-- 为 qa_records 增加 attachments JSON 字段，保存提问时上传的附件元数据
-- （name/type/size/url），用于历史会话回显缩略图/文件名/预览地址。
-- 不保存二进制内容；加性迁移，runner 对重复列幂等。
-- =========================================
ALTER TABLE qa_records
    ADD COLUMN IF NOT EXISTS attachments JSON NULL COMMENT '问答附件元数据（name/type/size/url）' AFTER pipeline_version_key;
