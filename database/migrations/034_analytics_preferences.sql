-- 模型分析默认设置（additive only）。
-- 用户可配置模型分析页的默认时间范围 / 时间粒度 / 消耗分布图类型 / 模型调用图类型。

ALTER TABLE user_preferences
    ADD COLUMN analytics_time_range VARCHAR(20) NOT NULL DEFAULT '1d' COMMENT '模型分析默认时间范围：1h/6h/1d/7d/30d',
    ADD COLUMN analytics_time_granularity VARCHAR(20) NOT NULL DEFAULT 'hour' COMMENT '模型分析默认时间粒度：hour/day',
    ADD COLUMN analytics_chart_type VARCHAR(20) NOT NULL DEFAULT 'bar' COMMENT '模型分析默认消耗分布图：bar/area',
    ADD COLUMN analytics_model_chart VARCHAR(20) NOT NULL DEFAULT 'trend' COMMENT '模型分析默认模型调用图：trend/distribution/ranking';
