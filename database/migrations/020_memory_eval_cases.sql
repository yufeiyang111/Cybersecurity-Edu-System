-- 持久记忆检索离线评测集（对标 rag_eval_cases）
CREATE TABLE IF NOT EXISTS memory_eval_cases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query TEXT NOT NULL COMMENT '评测问题',
    expected_content TEXT NOT NULL COMMENT '期望命中的记忆内容',
    category VARCHAR(32) NOT NULL DEFAULT 'fact' COMMENT '记忆分类',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='持久记忆检索评测集';

INSERT INTO memory_eval_cases (query, expected_content, category) VALUES
('用户关注哪个安全方向？', '用户负责公司安全运营，重点关注 Web 安全', 'fact'),
('用户平时用什么系统工作？', '用户使用 Linux 和 Windows 双环境进行安全工作', 'fact'),
('用户喜欢什么样的回答风格？', '用户偏好简洁直接的回答，不要长篇大论', 'preference'),
('用户对回答有什么格式要求？', '用户希望回答包含编号步骤和结论摘要', 'preference'),
('用户决定用什么数据库？', '项目数据库决定：使用 PostgreSQL 作为主库', 'decision'),
('用户今年的目标是什么？', '用户目标是三个月内通过 OSCP 认证', 'goal'),
('用户负责什么工作？', '用户是安全运营工程师，负责漏洞排查与应急响应', 'fact'),
('用户团队的规模？', '用户所在安全团队共 5 人，包含 2 名开发', 'fact'),
('用户偏好的会议形式？', '用户偏好 30 分钟以内的短会，会议要有明确结论', 'preference'),
('用户上一次的架构选择？', '决定采用微服务架构拆分安全网关模块', 'decision'),
('用户想学习什么技能？', '用户计划下半年学习云原生安全与容器安全', 'goal'),
('用户的客户类型？', '用户所在公司主要服务金融行业的客户', 'fact');
