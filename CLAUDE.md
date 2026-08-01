# CyberGuard 项目级 CLAUDE.md

## 项目结构

- 前端：`frontend/src/`
  - 页面：`views/`
  - 可复用 UI：`components/`
  - API 客户端：`api/`
  - 路由：`router/`
- 后端：`backend/app/`
  - 路由：`routes/`
  - 领域服务：`services/`
  - 数据模型：`models/`
  - 运维脚本：`scripts/`
- 数据库：`database/init.sql` 与 `database/migrations/`
- 测试：`backend/tests/`

## 强制模块化与复用规则

项目必须遵守 `.claude/rules/modular-architecture-and-reuse.md` 的全部要求，尤其是：

- 前端页面只负责编排；复杂弹窗、Finding 卡片、RAG 引用、Diff 展示、审核组件和数据加载逻辑必须按职责拆分。
- 后端路由保持薄层；鉴权、业务编排、外部调用、校验、审计、持久化和序列化必须在明确的领域模块中协作。
- 在新增实现前先搜索现有组件、服务、扫描器、Provider Adapter 和校验函数；相同逻辑出现两处时优先提取复用模块。
- 不创建无边界的万能 `utils` 或继续扩张巨型 `.vue` / `.py` 文件。
- 当文件超过约 250 行且职责持续增加，或一个模块承担超过 3 个独立职责时，必须优先拆分，并为拆分后的行为增加最小验证。

## 本项目的拆分偏好

- 安全工作台：页面在 `views/security/`，通用展示组件在 `components/security/`，安全 API 全部收敛到 `securityAPI`。
- 扫描与 Agent：按领域拆分到 `source_intake`、`github_source`、`dependency_scanner`、`security_knowledge`、`remediation_engine` 和语言扫描器模块；不要把它们重新合并进路由。
- 多语言扫描：新增语言只新增 Scanner 实现并注册到扫描器集合，保留现有扩展点。
- Agent 修复：Prompt 构造、代码上下文、Provider Adapter、JSON 解析、Patch 校验和持久化必须保持可独立测试的边界。

## 验证要求

- 后端改动：先运行受影响测试，再运行 `backend\venv\Scripts\python.exe -m pytest backend\tests -q`。
- 前端改动：运行 `npm --prefix frontend run build`；不要运行会自动改写全量文件的 lint 命令，除非明确确认变更范围。
- 数据库改动：只使用加性迁移，并同步维护 `database/init.sql`；未确认本机开发库前不得执行 MySQL 迁移。
