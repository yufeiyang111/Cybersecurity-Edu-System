-- 036：workspace 级 Agent v2 灰度降级开关（additive only）。
-- agent_feature_flags 允许在全局 env 总开关开启的前提下按 workspace 关闭
-- 指定能力（缩小灰度范围）；全局关闭的能力不能被 workspace 自行开启
-- （deny by default，未经授权的 workspace 无法开启高自治模式）。
-- 合法键：loop_v2 / event_schema_v2 / timeline_v2，值为布尔。

ALTER TABLE workspaces
    ADD COLUMN agent_feature_flags JSON NULL COMMENT 'workspace 级 v2 降级覆盖：{"loop_v2":false,"event_schema_v2":false,"timeline_v2":false}';
