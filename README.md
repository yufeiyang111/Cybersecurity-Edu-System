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

### 第一期限制

- 当前上传入口仅支持 ZIP；公开 GitHub 仓库导入在下一阶段实现。
- 当前内置语言规则仅覆盖 Python；JS/TS 和 Java 扫描器将按统一插件契约扩展。
- 当前只输出确定性扫描 Finding；受控 RAG 引用、Agent 研判和 Unified Diff 修复建议在下一阶段实现。
- 当前本地 ChromaDB 继续服务既有知识问答；安全知识来源治理和工作区检索过滤尚未接入。

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
