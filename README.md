# CyberGuard - 网络安全智能问答教学系统

基于检索增强生成（RAG）与大语言模型（LLM）的智能问答系统，专注于网络安全领域的教学支持。

## 功能特性

- **智能问答**：基于RAG技术，融合向量检索与知识图谱，提供精准的专业答案
- **知识库管理**：系统化的网络安全知识分类，支持多维度检索与浏览
- **知识图谱**：可视化展示知识点间的关联关系，支持多跳推理与关系探索
- **学习历史**：保存问答记录，支持收藏与回顾，让学习更连贯
- **用户管理**：完整的用户认证与权限管理系统
- **管理后台**：数据统计、用户管理、知识审核等功能

## 技术架构

### 后端技术栈
| 技术 | 说明 |
|------|------|
| Flask 3.x | Python Web框架 |
| SQLAlchemy | ORM数据库操作 |
| MySQL 8.0 | 关系型数据库 |
| ChromaDB | 向量数据库 |
| NetworkX | 知识图谱构建 |
| DashScope | 通义千问API |
| JWT | 用户认证 |

### 前端技术栈
| 技术 | 说明 |
|------|------|
| Vue.js 3.x | 前端框架 |
| Element Plus | UI组件库 |
| Pinia | 状态管理 |
| Vue Router | 路由管理 |
| ECharts | 数据可视化 |
| Vite | 构建工具 |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0
- 8GB+ RAM (向量模型需要)

### 2. 数据库配置

```bash
# 登录MySQL
mysql -u root -p

# 执行数据库初始化脚本
source database/init.sql
```

### 3. 后端部署

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 复制 .env.example 为 .env 并修改配置
cp .env.example .env

# 初始化数据库并填充示例数据
flask init-all

# 启动服务
python run.py
```

### 4. 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 5. 访问系统

- 前端地址：http://localhost:5173
- 后端API：http://localhost:5000

## 默认测试账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | 123456 |
| 教师 | teacher | 123456 |
| 普通用户 | user | 123456 |

## 项目结构

```
cyberguard/
├── backend/                      # 后端项目
│   ├── app/
│   │   ├── models/             # 数据模型
│   │   │   ├── user.py        # 用户模型
│   │   │   ├── knowledge.py   # 知识库模型
│   │   │   └── qa.py         # 问答模型
│   │   ├── routes/            # API路由
│   │   │   ├── auth.py       # 认证接口
│   │   │   ├── knowledge.py  # 知识库接口
│   │   │   ├── qa.py         # 问答接口
│   │   │   └── admin.py       # 管理接口
│   │   ├── services/          # 业务服务
│   │   │   ├── rag_engine.py # RAG核心引擎
│   │   │   ├── vector_store.py# 向量存储
│   │   │   └── graph_store.py # 知识图谱
│   │   ├── utils/            # 工具函数
│   │   │   ├── auth.py       # 认证工具
│   │   │   └── database.py   # 数据库工具
│   │   ├── config.py         # 配置文件
│   │   └── __init__.py       # 应用初始化
│   ├── requirements.txt
│   └── run.py                # 入口文件
│
├── frontend/                   # 前端项目
│   ├── src/
│   │   ├── api/              # API调用模块
│   │   ├── components/       # 公共组件
│   │   │   ├── StatCard.vue      # 统计卡片
│   │   │   ├── KnowledgeCard.vue # 知识卡片
│   │   │   ├── QuestionCard.vue  # 问答卡片
│   │   │   └── MarkdownRenderer.vue # Markdown渲染
│   │   ├── router/           # 路由配置
│   │   ├── stores/           # Pinia状态
│   │   ├── styles/           # 样式文件
│   │   └── views/            # 页面组件
│   │       ├── Home.vue          # 首页
│   │       ├── Login.vue        # 登录
│   │       ├── Register.vue      # 注册
│   │       ├── QA.vue           # 智能问答
│   │       ├── Knowledge.vue     # 知识库
│   │       ├── KnowledgeDetail.vue # 知识详情
│   │       ├── KnowledgeGraph.vue # 知识图谱
│   │       ├── user/            # 用户模块
│   │       └── admin/          # 管理模块
│   ├── package.json
│   └── vite.config.js
│
├── database/
│   └── init.sql              # 数据库初始化脚本
│
├── SPEC.md                    # 项目规范文档
└── README.md                  # 本文件
```

## API接口文档

### 认证接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /api/auth/register | 用户注册 | 否 |
| POST | /api/auth/login | 用户登录 | 否 |
| POST | /api/auth/logout | 用户登出 | 是 |
| GET | /api/auth/me | 获取当前用户 | 是 |
| PUT | /api/auth/profile | 修改个人信息 | 是 |
| PUT | /api/auth/password | 修改密码 | 是 |

### 知识库接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | /api/knowledge/categories | 获取分类列表 | 否 |
| GET | /api/knowledge | 获取知识列表 | 否 |
| GET | /api/knowledge/:id | 获取知识详情 | 否 |
| POST | /api/knowledge | 创建知识条目 | 教师 |
| PUT | /api/knowledge/:id | 更新知识条目 | 教师 |
| DELETE | /api/knowledge/:id | 删除知识条目 | 教师 |
| GET | /api/knowledge/search | 搜索知识 | 否 |
| GET | /api/knowledge/hot | 热门知识 | 否 |

### 问答接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /api/qa/ask | 提交问题 | 用户 |
| GET | /api/qa/history | 获取问答历史 | 用户 |
| GET | /api/qa/:id | 获取问答详情 | 用户 |
| POST | /api/qa/:id/feedback | 提交反馈 | 用户 |
| GET | /api/qa/suggestions | 追问建议 | 否 |
| GET | /api/qa/similar | 相似问题 | 否 |
| POST | /api/qa/favorites | 添加收藏 | 用户 |
| DELETE | /api/qa/favorites/:id | 取消收藏 | 用户 |

### 管理接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | /api/admin/stats/overview | 系统概览 | 管理员 |
| GET | /api/admin/users | 用户列表 | 管理员 |
| PUT | /api/admin/users/:id | 更新用户 | 管理员 |
| DELETE | /api/admin/users/:id | 删除用户 | 管理员 |
| GET | /api/admin/knowledge/manage | 知识管理 | 管理员 |
| POST | /api/admin/knowledge/:id/audit | 审核知识 | 管理员 |
| GET | /api/admin/graph/nodes | 图谱节点 | 管理员 |
| GET | /api/admin/graph/edges | 图谱边 | 管理员 |
| POST | /api/admin/vector/rebuild | 重建索引 | 管理员 |

## RAG引擎说明

### 工作流程

```
用户问题 → 问题理解 → 查询构建
                         ↓
                   ┌─────┴─────┐
                   ↓           ↓
             向量检索      知识图谱检索
                   ↓           ↓
                   └─────┬─────┘
                         ↓
                   结果融合排序(RRF)
                         ↓
              ┌───────────┴───────────┐
              ↓                       ↓
         上下文构建              Prompt工程
              ↓                       ↓
              └───────────┬───────────┘
                          ↓
                   LLM生成引擎
                          ↓
                    答案后处理
                          ↓
              答案 + 知识来源 + 置信度
```

### 向量检索配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| VECTOR_TOP_K | 10 | 返回的Top-K结果数 |
| SIMILARITY_THRESHOLD | 0.5 | 相似度阈值 |
| MAX_CONTEXT_LENGTH | 4000 | 最大上下文长度 |

### 知识图谱配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| GRAPH_MAX_HOPS | 3 | 最大跳数 |
| GRAPH_WEIGHT_DECAY | 0.8 | 权重衰减系数 |

## 环境变量配置

```env
# 数据库
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=cyberguard

# JWT
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# 通义千问API
DASHSCOPE_API_KEY=your_api_key
DASHSCOPE_MODEL=qwen-plus

# RAG
VECTOR_TOP_K=10
SIMILARITY_THRESHOLD=0.5
```

## License

MIT License

---

## 企业级安全工作台（第一阶段）

CyberGuard 正在从“网络安全知识问答教学系统”升级为 **Agent + RAG 安全运营与 DevSecOps 协同平台**。第一阶段已经交付一个可验证的安全扫描闭环：创建项目、上传 ZIP、生成不可变快照、执行只读静态扫描、保存脱敏风险证据、展示项目任务与风险概要。

### 已实现能力

- **工作区安全边界**：安全项目、快照、任务、Finding 和审计事件均属于工作区；后端为既有用户创建确定性的个人默认工作区。
- **安全 ZIP 接入**：拒绝路径穿越、绝对/Windows 驱动器路径、符号链接、加密条目、特殊文件、超量文件与 Zip Bomb；只提取允许的 UTF-8 源码/配置/依赖清单。
- **绝不执行用户项目**：平台不会 `pip install`、`npm install`、构建、测试、导入或运行上传项目中的任何代码。
- **Python 基线规则**：检测 `subprocess(..., shell=True)`（CWE-78）、不安全 `yaml.load`（CWE-502）、`app.run(debug=True)`（CWE-489）以及疑似硬编码敏感信息（CWE-798）。
- **证据优先**：Finding 保存规则、CWE、文件位置、稳定指纹和脱敏证据；秘密类证据仅保留掩码和 SHA-256 摘要，不保存原值。
- **异步演进接口**：开发模式可内联执行；生产可启用 Redis + RQ。队列只传递扫描任务 ID，Worker 自己建立应用上下文。
- **审计和可复现性**：项目快照保存内容 SHA-256；上传和扫描完成/失败事件写入审计表。
- **前端安全工作台**：登录后进入“安全工作台”，创建项目、上传 ZIP、查看任务进度、风险概要和脱敏证据。

### 第一期基线与后续演进

- 第一期建立 ZIP 导入、Python 规则扫描、脱敏 Finding 与审计闭环；Phase 2 已在下文扩展为公开 GitHub 固定提交快照、JS/TS 与 Java 扫描器、依赖库存和 OSV SCA。
- 当前只读扫描边界保持不变：平台不会安装依赖、构建、测试、导入或执行任何上传或导入的项目代码。
- 受控 RAG 引用、Agent 研判和 Unified Diff 修复建议，以及安全知识来源治理与工作区检索过滤，见下文的 Phase 3 说明。

### 本地运行（安全扫描闭环）

1. 在 MySQL 初始化现有数据库后，应用新增的**加性**安全扫描迁移（不会删除已有表）：

```powershell
cd backend
.\venv\Scripts\python.exe -m flask --app run apply-security-migrations
```

2. 开发时使用内联扫描（`.env` 中保持 `RQ_ASYNC=false`），启动后端：

```powershell
cd backend
.\venv\Scripts\python.exe run.py
```

3. 若使用真实异步扫描，先启动 Redis，并在 `.env` 设置 `RQ_ASYNC=true` 与有效 `REDIS_URL`，然后另开终端：

```powershell
cd backend
.\venv\Scripts\python.exe -m flask --app run rq-worker
```

4. 启动前端：

```powershell
cd frontend
npm run dev
```

登录后进入 **安全工作台**，创建项目并上传包含 Python 源码的 ZIP。例如 `subprocess.run(cmd, shell=True)` 应生成 `PY-SHELL-TRUE` 高危 Finding。

### 验证记录（2026-07-19）

| 命令 | 结果 | 说明 |
|---|---|---|
| `backend\\venv\\Scripts\\python.exe -m pytest backend\\tests -q` | 通过 | 安全配置、模型、工作区授权、ZIP 防护、Python 扫描器、编排和 API 回归。 |
| `npm --prefix frontend run build` | 通过 | 安全工作台页面、路由和 API 集成可以生产构建。 |

> 尚未在本机执行 MySQL 加性迁移或真实 Redis Worker 烟测，原因是它们依赖本地服务状态；执行前请确认使用开发数据库，切勿对生产库直接试运行。

---

## Phase 2：GitHub 导入、多语言 SAST 与 SCA

第二阶段将安全工作台扩展为可用于 DevSecOps 演示的多源代码审计闭环：公共 GitHub 仓库只会被下载为固定 Commit 的 ZIP 快照，随后进入与本地 ZIP 相同的只读安全解压和静态分析流程。

### 已实现能力

- **受限 GitHub 导入**：只接受 `https://github.com/{owner}/{repo}` 形式的公开仓库地址；拒绝 Token、SSH、端口、IP、额外路径、查询参数和片段。
- **固定提交快照**：先通过 GitHub API 解析默认分支与 Commit SHA，再从受验证归档域名下载 ZIP；不使用 `git clone`，不会执行 Hook、Submodule、LFS 或仓库代码。
- **多语言 SAST**：
  - Python：`shell=True`、危险 YAML 反序列化、Flask Debug、硬编码敏感信息。
  - JavaScript / TypeScript：`eval`、`child_process`、`dangerouslySetInnerHTML`、宽松 CORS。
  - Java：Runtime 命令执行、`ObjectInputStream`、XXE 工厂、宽松 CORS。
- **依赖清单与 SCA**：解析 Python、Node.js 与 Java 的主流依赖文件；OSV 查询只发送 `{ecosystem, package_name, version}`，不发送源码、仓库地址、文件路径、用户身份或密钥。
- **失败可见但不泄露**：外部 SCA 调用失败会转化为安全警告，扫描任务可标记为 `completed_with_warnings`，不会输出第三方错误正文。

### 启用 OSV SCA

默认 `SCA_OSV_ENABLED=false`，确保本地演示不依赖外部情报网络。确认合规后可在 `.env` 中显式开启：

```dotenv
SCA_OSV_ENABLED=true
SCA_OSV_API_URL=https://api.osv.dev/v1/querybatch
```

### Phase 2 安全边界

- 不执行 ZIP 或 GitHub 仓库中的任何文件，也不安装依赖、构建项目或启动 Hook。
- ZIP 与 GitHub 归档复用路径穿越、Zip Bomb、符号链接、特殊文件、文件数量和解压体积防护。
- SAST、Secret 与 SCA 统一持久化为证据化 Finding；展示层只读取脱敏证据。
- GitHub 网络访问固定在允许的 GitHub API 与归档域名，并对重定向进行约束性验证。

## 企业级 Agent + RAG 安全运营闭环（Phase 3）

在已有 ZIP / 公共 GitHub 仓库安全导入、多语言 SAST 与 OSV SCA 的基础上，CyberGuard 现已形成面向 **SOC / DevSecOps** 的可信修复建议闭环：

```text
不可变项目快照
  → Python / JavaScript / TypeScript / Java 静态扫描与 SCA
  → 证据化 Finding（默认脱敏）
  → 工作区级、版本化安全知识 RAG
  → 受限上下文修复 Agent
  → 严格 Unified Diff 校验
  → 人工审核与审计事件
```

### Phase 3 核心能力

- **工作区隔离的安全知识库**：知识来源与文档具有来源版本、文档版本、有效期、启停状态和审计记录；检索首先执行确定性词法排序，可选 Chroma 向量索引失败时会静默退化，不会跨工作区返回资料。
- **可信修复 Agent**：修复 Agent 只接收标准化 Finding、已脱敏证据、工作区授权的 RAG 引用以及受限的局部代码窗口；不会读取完整仓库、用户身份、归档绝对路径或未脱敏密钥。
- **Secret 防泄露边界**：Secret 类 Finding 不会把原文件上下文发给模型；知识检索片段、RAG 向量文本和前端展示内容均使用脱敏内容。
- **LLM 可控降级**：`REMEDIATION_LLM_ENABLED=false` 为默认值。未启用、未配置密钥、Provider 请求失败或模型输出不合法时，系统会退回规则化建议，而不会阻塞扫描任务。
- **安全 Diff 防线**：只接受目标 Finding 对应的单文件 Unified Diff；拒绝绝对路径、`..`、多文件、二进制、超限、无上下文和上下文不匹配的补丁。系统从不自动应用、执行、提交或推送 Agent 生成的补丁。
- **人工审核与可追溯性**：建议状态只能是 `pending`、`accepted`、`rejected` 或 `needs_revision`；所有生成、审核、知识来源和知识文档操作都会写入不包含正文、代码、Prompt、Diff 或密钥的审计元数据。

### 新增安全运营 API

| 接口 | 说明 | 最低工作区角色 |
| --- | --- | --- |
| `POST /api/security/knowledge/sources` | 创建受治理的知识来源 | owner / security_admin |
| `GET /api/security/knowledge/sources` | 列出本工作区知识来源元数据 | owner / security_admin |
| `POST /api/security/knowledge/sources/{id}/documents` | 创建版本化知识文档 | owner / security_admin |
| `GET /api/security/knowledge/sources/{id}/documents` | 列出文档元数据（不返回正文） | owner / security_admin |
| `POST /api/security/findings/{id}/suggestions` | 为已授权 Finding 生成修复建议 | owner / security_admin / analyst / developer |
| `GET /api/security/findings/{id}/suggestions` | 查看 Finding 的历史修复建议 | 任意有项目读取权限成员 |
| `POST /api/security/suggestions/{id}/review` | 记录接受、拒绝或需要修改的审核决定 | owner / security_admin / analyst / developer |

### 本地演示路径

1. 进入“项目安全工作台”，创建项目并上传一个 ZIP，或导入符合约束的公共 GitHub 仓库。
2. 等待扫描任务完成，在项目详情中选择一个 Finding。
3. 进入“安全知识治理”，先创建来源与版本化文档；页面不会回显文档正文。
4. 回到项目详情，点击“生成修复建议”。默认规则化模式可在不配置外部 LLM 的情况下运行。
5. 查看 RAG 引用、警告代码和可选 Diff；仅可复制 Diff 到独立分支进行验证。
6. 使用“人工审核”记录 `accepted`、`rejected` 或 `needs_revision`，在审计表中追溯操作。

### Phase 3 环境变量

```dotenv
# 是否启用专属安全知识向量索引。关闭时仍会使用工作区隔离的词法检索。
SECURITY_KNOWLEDGE_VECTOR_ENABLED=false

# 修复 Agent 默认不调用外部模型；开启时仍要求配置相应 Provider 密钥。
REMEDIATION_LLM_ENABLED=false
REMEDIATION_MAX_CONTEXT_CHARS=12000
REMEDIATION_MAX_OUTPUT_CHARS=8000
REMEDIATION_RETRIEVAL_TOP_K=5
REMEDIATION_PATCH_MAX_LINES=500
REMEDIATION_PATCH_MAX_CHARS=50000
```

### 验证记录（2026-07-31）

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests -q
# 129 passed
.\backend\venv\Scripts\python.exe -m compileall backend\app
# completed without compilation errors
npm --prefix frontend run build
# build succeeded
```

数据库验证：模型与 API 使用 SQLite 内存库完成自动化测试；2026-07-19 已在本机 `cyberguard` 开发库完成 MySQL 8 加性迁移 `001 → 002 → 003` 的真实执行和表结构核验。迁移前已导出仅结构备份；不要将这一流程直接用于未确认或生产环境。

## Phase 4：生产化可靠性与安全运营

Phase 4 在 Phase 1-3 的扫描、SCA、知识 RAG 和可信修复边界之上，补齐任务恢复、运行时健康检查和生产化运维能力。

### 任务可靠性

- `ScanTask` 使用内容快照复用、唯一 `dispatch_key` 和条件 worker 抢占，避免相同快照重复创建或重复执行。
- 任务支持受保护的取消和失败/取消重试；重试次数由 `SCAN_TASK_MAX_RETRIES` 限制，默认值为 3，最大值为 10。
- 队列派发失败会写入 `SCAN_DISPATCH_FAILED`，不会让任务永久停留在 `created` 状态。
- 重试只复用不可变快照，Finding、依赖和证据写入保持指纹/坐标幂等；系统不会执行被扫描项目代码。

### 健康检查与可观测性

- `/api/health` 和 `/api/health/live` 只表示进程存活，不访问外部服务。
- `/api/health/ready` 检查数据库和工作区存储；Neo4j、Chroma 和 LLM Provider 只返回是否配置或是否启用，不会被 readiness 请求擅自联网探测。
- 每个请求返回受限的 `X-Request-ID`，调用链可以使用该值关联日志；输入过长或包含路径穿越字符的关联 ID 会被替换。
- 健康响应、任务错误和审计元数据不包含密码、Token、Prompt、完整异常、原始代码或外部连接串。

### 权限与前端边界

- 取消和重试要求项目工作区的写角色，查询仍然执行工作区读取鉴权。
- 前端任务表提供取消、重试和 loading 状态；这些操作由后端再次授权，不能依赖前端隐藏按钮。
- 修复建议 Diff 仍然只能查看、复制和人工审核，不提供自动应用、执行、提交或推送入口。

### 数据库迁移

Phase 4 使用加性迁移 `004_phase4_task_reliability.sql`，为历史 `scan_tasks` 增加可为空的派发键和默认重试计数，并补充唯一约束与索引。迁移由有序迁移 runner 管理；本地初始化 SQL 已同步。未在本阶段执行生产数据库迁移。

### Phase 4 验证记录（2026-07-31）

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests -q
# 158 passed
.\backend\venv\Scripts\python.exe -m compileall backend\app
# completed without compilation errors
npm --prefix frontend run build
# build succeeded
```


外部 GitHub、OSV、Neo4j、Chroma 和 LLM Provider 的真实连通性不属于默认测试路径；相关检查必须显式执行，并且不能把配置存在误报为服务可用。