# CyberGuard — 企业级 Agent + RAG 安全运营 / DevSecOps 工作台

CyberGuard 用于导入 ZIP 或公共 GitHub 项目，建立不可变项目快照，执行确定性安全扫描、依赖漏洞分析（OSV SCA）与 Secret 检测，并通过统一 Finding、可解释风险评分、RAG 引用和可选 LLM Provider 提供可追溯的安全分析与人工审核修复建议。

核心定位不是“调用大模型生成一段安全文案”，而是：

```text
安全项目导入 → 快照隔离 → 多语言 Scanner → Secret / SCA
→ Finding 归一化 → 风险评分 → RAG 引用 → 可选 LLM 研判
→ 受限 Diff → 人工审核 → 审计追踪
```

## 核心能力

- **安全项目导入**：ZIP 上传或公共 GitHub 仓库（固定 Commit 快照）；拒绝路径穿越、绝对/Windows 驱动器路径、符号链接、加密条目、Zip Bomb 与超量文件。
- **不可变快照隔离**：每个项目保存内容 SHA-256，绝不执行被扫描项目中的任何代码（不安装依赖、不构建、不导入、不运行）。
- **多语言 SAST**：Python / JavaScript / TypeScript / Java 确定性规则扫描 + Secret 检测。
- **SCA 依赖分析**：解析主流依赖清单，仅向 OSV 发送 `{ecosystem, package, version}`，支持失败降级与缓存。
- **统一 Finding 模型**：跨 Scanner 去重、稳定 fingerprint、脱敏证据（秘密只保留掩码与 SHA-256 摘要）。
- **可解释风险评分**：不依赖 LLM，基于 10 个风险因子输出 0~100 分与 critical/high/medium/low 优先级，并给出因子级说明。
- **受治理安全知识 RAG**：工作区隔离、版本化知识来源与文档；向量索引失败时自动降级到词法检索。
- **可信修复 Agent**：仅接收标准化 Finding、脱敏证据、工作区授权的 RAG 引用与受限局部代码窗口；输出经过严格 Unified Diff 校验。
- **人工审核闭环**：建议仅可接受/拒绝/要求修改，全程审计；从不自动应用、执行、提交或推送补丁。
- **Provider 健康检查与降级**：MiniMax / DashScope Adapter + 规则化 Provider，统一契约、超时、冷却与安全序列化。
- **任务可靠性**：快照复用、`dispatch_key` 去重、条件 Worker 抢占、受保护取消与重试、扫描器/SCA 失败隔离。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Flask 3.x、SQLAlchemy、Redis + RQ（可选异步）、Chroma（可选向量）、OSV API |
| 前端 | Vue 3、Element Plus、Pinia、Vue Router、Vite |
| 数据库 | MySQL 8.0（`database/init.sql` + 加性迁移） |
| 安全 | JWT、工作区级鉴权、脱敏证据、审计事件、限流 |

## 项目结构

```text
backend/app/
├── routes/
│   ├── auth.py                    # 认证
│   ├── projects.py                # 项目导入
│   ├── llm_health.py              # LLM Provider 健康检查
│   └── security/                  # 安全运营路由（薄层）
│       ├── common.py              # 鉴权/参数校验共享逻辑
│       ├── projects.py            # 安全项目
│       ├── snapshots.py           # ZIP / GitHub 快照
│       ├── tasks.py               # 扫描任务 / Finding / 依赖
│       ├── knowledge.py           # 安全知识治理
│       └── remediation.py         # 修复建议与审核
├── services/
│   ├── llm/                       # 统一 LLM Provider（contracts/fallback/health）
│   ├── scanners/                  # Scanner 插件（registry/normalizer/base + 语言实现）
│   ├── remediation/               # 可信修复 Agent（context/patch_validator/providers）
│   ├── risk_scoring.py            # 可解释风险评分
│   ├── scan_execution.py          # 扫描执行
│   ├── scan_task_lifecycle.py     # 任务生命周期
│   ├── snapshot_service.py        # 快照服务
│   ├── github_source.py           # GitHub 受限导入
│   ├── dependency_scanner.py      # 依赖清单解析
│   ├── osv_client.py              # OSV SCA 客户端
│   ├── security_knowledge.py      # 安全知识 RAG
│   └── runtime_health.py          # 运行时健康
└── models/                        # SQLAlchemy 数据模型

frontend/src/
├── api/                           # API 客户端
├── components/security/           # 安全工作台可复用组件（Finding 卡片、Diff 查看、知识治理等）
├── composables/security/          # 数据加载与交互逻辑
├── features/security/             # 展示/格式化工具
├── views/security/                # 页面编排
└── router/

database/
├── init.sql
└── migrations/                    # 001~004 加性迁移
```

## 快速开始

### 1. 环境要求

- Python 3.10+、Node.js 18+、MySQL 8.0
- 可选：Redis（异步扫描）、MiniMax / DashScope 密钥（LLM 研判）

### 2. 数据库

```powershell
# 确认 MySQL 服务运行
Get-Service MySQL80
```

按顺序执行加性迁移（迁移 runner 见 `backend/app/scripts/apply_sql_migration.py`），或使用 `database/init.sql` 初始化开发库。**只使用加性迁移，不要在生产库执行 reset / drop / truncate。**

### 3. 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
# 复制 .env.example 为 .env 并填写真实配置
.\venv\Scripts\python.exe run.py
```

后端地址：`http://127.0.0.1:5001`，健康检查：`Invoke-RestMethod http://127.0.0.1:5001/api/health`

可选异步扫描：设置 `RQ_ASYNC=true` 并配置 `REDIS_URL`，另开终端执行 `.\venv\Scripts\python.exe -m flask --app run rq-worker`。

### 4. 前端

```powershell
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`（Vite 将 `/api` 代理到 `http://localhost:5001`）。

## 核心 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST / GET | `/api/auth/login`、`/api/auth/me` | 认证 |
| POST | `/api/security/projects` | 创建安全项目 |
| GET | `/api/security/projects` | 项目列表 |
| POST | `/api/security/projects/{id}/snapshots:upload` | 上传 ZIP 建立快照 |
| POST | `/api/security/projects/{id}/snapshots:github` | 导入公共 GitHub 仓库 |
| GET | `/api/security/projects/{id}/tasks` | 任务列表 |
| GET | `/api/security/tasks/{id}/findings` | Finding 列表（`?sort=risk` 风险排序） |
| POST | `/api/security/tasks/{id}/cancel` / `retry` | 取消 / 重试任务 |
| GET | `/api/security/projects/{id}/dependencies` | 依赖清单与 SCA 结果 |
| POST / GET | `/api/security/knowledge/sources` | 知识来源治理 |
| POST / GET | `/api/security/knowledge/sources/{id}/documents` | 版本化知识文档（不返回正文） |
| POST / GET | `/api/security/findings/{id}/suggestions` | 生成 / 查看修复建议 |
| POST | `/api/security/suggestions/{id}/review` | 人工审核 |
| GET | `/api/health`、`/live`、`/ready` | 健康检查 |
| GET / POST | `/api/health/llm-providers` | LLM Provider 健康检查 |

## 安全边界与设计原则

- **不执行用户项目**：平台从不上传项目的代码上运行任何命令、安装依赖或执行 Hook。
- **脱敏证据**：Finding 只保存证据掩码与 SHA-256；Secret 类 Finding 的原文上下文从不发给模型。
- **受限修复 Agent**：只接收最小化上下文与工作区授权的 RAG 引用；Patch 必须通过严格 Unified Diff 校验。
- **健康检查不联网**：readiness 只检查数据库与工作区存储；外部服务仅报告“已配置”，不被擅自探测。
- **敏感信息不外泄**：健康响应、任务错误、审计元数据均不含密码、Token、Prompt、完整异常或连接串。
- **鉴权下沉后端**：取消、重试、生成建议等操作均在后端二次授权，不依赖前端隐藏按钮。

## 可解释风险评分

`GET /api/security/tasks/{id}/findings?sort=risk` 返回：

```json
{
  "risk": {
    "score": 72.5,
    "priority": "high",
    "policy_version": "risk-v1",
    "factors": [],
    "explanation": "..."
  }
}
```

评分不依赖 LLM。风险上下文（`internet_exposure`、`asset_criticality`、`data_sensitivity`、`dependency_reachability`）在未接入真实 CMDB / 资产平台 / 依赖调用图时使用默认或规则推断值。

## 环境变量

完整配置项见 `backend/.env.example`。核心项：

```dotenv
# 数据库
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change-me
MYSQL_DATABASE=cyberguard

# 认证
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# LLM（可选，默认规则化模式）
DASHSCOPE_API_KEY=your_api_key
DASHSCOPE_MODEL=qwen-plus
MINIMAX_API_KEY=your_api_key
MINIMAX_MODEL=your_model
REMEDIATION_LLM_ENABLED=false

# 安全知识向量（可选，默认词法检索）
SECURITY_KNOWLEDGE_VECTOR_ENABLED=false

# SCA（默认关闭，避免演示依赖外网）
SCA_OSV_ENABLED=false
SCA_OSV_API_URL=https://api.osv.dev/v1/querybatch

# 异步扫描（可选）
RQ_ASYNC=false
REDIS_URL=redis://localhost:6379/0
```

## 测试与验证

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests -q
.\backend\venv\Scripts\python.exe -m compileall backend\app
npm --prefix frontend run build
```

当前测试基线：后端 169 项通过；前端生产构建通过。外部服务（MiniMax、DashScope、GitHub、OSV、Neo4j、Chroma）的真实连通性不属于默认测试路径，须显式验收，不能把“配置存在”误报为“服务可用”。

## License

MIT License
