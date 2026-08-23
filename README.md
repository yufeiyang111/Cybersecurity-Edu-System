# CyberGuard

<div align="center">

**基于检索增强生成（RAG）的网络安全知识问答平台**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat)
![Flask](https://img.shields.io/badge/Flask-3.0-111111?style=flat)
![Vue](https://img.shields.io/badge/Vue-3.4-42B883?style=flat&logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF?style=flat&logo=vite&logoColor=white)
![Element Plus](https://img.shields.io/badge/Element_Plus-2.4-409EFF?style=flat)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?style=flat&logo=mysql&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-1.19-DC382D?style=flat)
![Backend Tests](https://img.shields.io/badge/Backend_Tests-1429_PASS-brightgreen?style=flat)
![Eval Cases](https://img.shields.io/badge/Eval_Cases-1422-FF6F00?style=flat)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

</div>

---

CyberGuard 是一个以 RAG 为核心的网络安全知识问答平台：Flask 后端 + Vue 3 前端，将 1000+ 篇开源安全文档结构化入库（约 2.2 万知识块），经混合检索、两阶段重排与严格引用校验，产出可溯源到原文行号的回答。配套全覆盖离线评测体系——**1422 道评测题**、人工审批工作流与一键真实链路评测。它解决两个核心问题：

1. **答案可溯源**。回答中的每个论断都标注引用编号（`[C-n]`），引用必须来自真实检索命中的知识块，并精确到原文行号；引用无法通过校验时系统降级处理而不是放行编造内容。
2. **质量可度量**。内置版本化评测数据集、审批工作流与一键真实链路评测脚本，检索命中率（Recall@k）、排序质量（MRR / NDCG）、证据覆盖与引用合法性均有量化基线，回归可对比。

## 特性

- **结构化语料库**：开源安全文档经标题/章节解析入库，携带分类、难度、标签、来源字段，当前规模约 1000+ 篇文档、2 万+ 知识块。
- **混合检索**：Qdrant 双路召回（dense 向量 + BM25 词法），RRF 融合，叠加知识图谱扩展，按文档去重后送入重排。
- **两阶段重排**：bge-reranker-v2-m3 对候选证据精排，控制进入上下文的噪声。
- **行号级引用**：分块时保留整文档行号区间，回答引用可定位到「第 X–Y 行」。
- **严格引用校验**：strict 模式下引用必须属于本次证据包，伪造或越界引用触发降级而非输出。
- **无据回答兜底**：未检索到证据时默认拒答；用户显式开启后可输出明确标记的无依据通用回答（不带任何引用）。
- **全链路审计**：执行链路记录 Trace（不含用户 query 原文与密钥），问答检索日志落库用于离线评估。
- **离线评测体系**：三套版本化数据集、人工审批工作流、一键真实链路评测、HTML / Word 报告与发布门禁。

## 目录

- [系统架构](#系统架构)
- [RAG 知识问答](#rag-知识问答)
  - [整体链路](#整体链路)
  - [语料与文档来源](#语料与文档来源)
  - [文档解析与分块](#文档解析与分块)
  - [向量生成与索引](#向量生成与索引)
  - [混合检索与重排](#混合检索与重排)
  - [证据打包与引用校验](#证据打包与引用校验)
  - [无据回答兜底](#无据回答兜底)
  - [评测体系](#评测体系)
  - [评测基线](#评测基线)
- [快速开始](#快速开始)
- [常用命令](#常用命令)
- [目录结构](#目录结构)
- [测试](#测试)
- [许可证](#许可证)

## 系统架构

```text
┌──────────┐   ┌─────────────┐   ┌──────────────────────────────┐
│ 前端 SPA  │──▶│ Flask API   │──▶│ RAG 引擎                      │
│ Vue 3    │   │ JWT 认证     │   │ 检索 → 重排 → 证据 → 生成      │
└──────────┘   └─────────────┘   └───┬──────────┬─────────┬───────┘
                                     │          │         │
                              ┌──────▼───┐ ┌────▼────┐ ┌──▼──────────┐
                              │ Qdrant   │ │ Neo4j   │ │ LLM Provider│
                              │ 向量检索  │ │ 知识图谱 │ │ MiniMax 等  │
                              └──────────┘ └─────────┘ └─────────────┘
```

## RAG 知识问答

### 整体链路

```text
开源安全文档 ─▶ 结构化解析 ─▶ 分块（384 token，保留行号）
    ─▶ bge-m3 向量化 ─▶ Qdrant 入库（dense + BM25 sparse）
查询 ─▶ 混合召回（dense + BM25，RRF 融合）─▶ 知识图谱扩展 ─▶ 去重
    ─▶ bge-reranker 重排 ─▶ 证据打包（token 预算 + 行号）
    ─▶ LLM 生成（引用标注 [C-n]）─▶ 引用校验 ─▶ 回答 / 拒答
```

### 语料与文档来源

- 语料存储于 `knowledge_items` 表，当前包含 16 个分类：安全方法论、渗透测试、Web 安全、系统安全、二进制安全、移动安全、macOS 安全、AI 安全、密码学、数据安全、应急响应、区块链安全、物联网与硬件安全等。
- 内容由两部分组成：
  - **开源社区知识的中文整理**：主要来自 [HackTricks](https://github.com/HackTricks-wiki/hacktricks)（作者 Carlos Polop）的中文翻译。该内容版权归原项目所有，遵循其原始许可证（署名—非商业性使用，商用需另行授权），本项目的整理仅用于学习与研究目的；
  - **自撰教程**：项目自有的基础安全教程与示例数据。
- 每篇文档携带 `category_id / difficulty / source / tags` 元数据，供过滤与评测分组使用。

### 文档解析与分块

- 解析后的正文按 Markdown 标题层级做结构化切分，分块大小 384 token，优先使用 AutoTokenizer 真实计数，模型不可用时回退字符估算。
- 每个知识块携带 `doc_id / chunk_index / start_line / end_line / parent_text`：
  - 行号区间支撑前端「第 X–Y 行」引用定位；
  - `parent_text` 用于父子窗口合成——检索命中小块，回填更大上下文。

### 向量生成与索引

| 组件 | 实现 |
|---|---|
| Embedding | BAAI/bge-m3，1024 维；默认走 SiliconFlow API，本地模型作为降级链 |
| 词法向量 | jieba 分词词频 sparse vector，Qdrant `modifier=idf` 原生 BM25 |
| 存储 | Qdrant 命名向量 collection：公共库 `knowledge_embeddings`，工作区私有库 `security_knowledge_embeddings` |

Embedding 服务不可用时自动降级（本地 bge-m3 → 轻量备选模型 → 词袋），维度不一致期间检索自动退化为纯词法路径，保证可用性。

### 混合检索与重排

1. 同一查询发起 dense 与 BM25 两路召回，Qdrant Query API 执行，本地 RRF 融合排序；
2. 叠加知识图谱扩展关联实体（Neo4j 不可用时自动降级 NetworkX 内存图）；
3. 按 `doc_id` 去重后交由 bge-reranker-v2-m3 精排，取 Top-N 进入证据包；
4. 全程记录各阶段耗时（retrieval_ms / rerank_ms）用于性能回归。

### 证据打包与引用校验

- 证据包受 token 预算约束，超限时按相关性截断；
- 生成阶段要求模型对每个论断标注 `[C-n]` 引用编号；
- strict 校验模式下，引用必须指向本次证据包内的知识块，出现未知引用即判定失败并走降级输出；
- 未通过校验的回答不会以正常形态展示给用户。

### 无据回答兜底

- 默认行为：未检索到任何证据时不调用生成，直接返回「证据不足」。
- 用户可在设置中显式开启 `allow_ungrounded_answers`：此时允许模型输出通用回答，但回答前置醒目提示、引用为空，并记录 `NO_RETRIEVED_EVIDENCE` 与 `USER_APPROVED_UNGROUNDED_ANSWER` 审计码。
- 该开关为用户级持久化偏好，仅影响开启者本人的问答体验。

### 评测体系

评测相关代码位于 `backend/app/services/rag_core/datasets/` 与 `backend/app/scripts/`：

| 脚本 | 作用 |
|---|---|
| `export_rag_eval_corpus.py` | 只读导出语料正文与向量分块元数据（生成评测集的事实来源） |
| `generate_rag_eval_from_corpus.py` | 从导出快照确定性生成模板广度评测集 |
| `build_curated_rag_eval.py` | 校验人工策展查询表并回填真实行号 |
| `export_eval_review_sheet.py` | 导出人工审批清单（CSV / JSONL） |
| `run_rag_eval_suite.py` | 一键真实链路评测（按审批状态过滤用例） |
| `render_eval_report.py` | 渲染 HTML 交互报告与 Word 报告 |
| `rag_evaluate.py` | 兼容历史基线的离线评估入口 |

三套版本化数据集：

| 数据集 | 规模 | 说明 |
|---|---|---|
| `production_rag_eval_curated_v1` | 1021 题 | 覆盖全部真实文档，query 由人工逐篇撰写 |
| `production_rag_eval_v1` | 255 题 | 模板生成的广度集 |
| `public_rag_eval_v1` | 151 题 | 样例语料精策集（含拒答与对抗用例） |

所有 gold evidence 的 `chunk_id / start_line / end_line` 直接取自真实索引 payload，构建期逐字校验锚句存在性，不存在人工编造行号的可能。

评测执行支持人工审批工作流：先在导出的 CSV 中将用例标记为 approved / rejected，评测脚本只运行 approved 用例，结果输出汇总报告（JSON）、逐题明细（JSONL）与可视化报告（HTML / Word）。

### 评测基线

以下为 curated 数据集全量 1016 题（语料去重后）在真实链路（bge-m3 + Qdrant + mimo-v2.5）下的实测结果：

| 指标 | 数值 |
|---|---|
| Recall@1 | 79.0% |
| Recall@3 | 91.9% |
| Recall@5 | 94.3% |
| MRR | 0.860 |
| NDCG@10 | 0.886 |
| Supported 答案率 | 88.7% |
| 证据覆盖率 | 95.1% |
| 引用归属校验 | 1016/1016（0 未知引用、0 畸形论断） |
| 检索延迟 P50 / P95 | 936 ms / 1332 ms |
| LLM-as-judge 忠实度 | 0.732（均值，满分 1.0） |
| LLM-as-judge 相关性 | 0.960（均值，满分 1.0） |

## 快速开始

### 环境要求

- Python 3.10+、Node.js 18+、MySQL 8.0
- Qdrant 1.10+（默认 `http://127.0.0.1:6333`）
- 可选：Redis（异步任务）、Neo4j（知识图谱，不可用时自动降级）
- `.env` 中配置 SiliconFlow 密钥（Embedding / Rerank）与 LLM Provider（也可在系统内以用户维度配置）

### 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
Copy-Item .env.example .env   # 按注释填写数据库 / Redis / API Key
.\venv\Scripts\python.exe run.py
```

后端地址 `http://127.0.0.1:5001`，健康检查 `GET /api/health`。

### 数据库与迁移

```powershell
cd backend
$env:FLASK_APP = "run.py"
.\venv\Scripts\flask.exe --app run apply-security-migrations
```

迁移 runner 幂等，按序补齐 `database/migrations/` 中所有未应用的加性迁移；首次部署也可直接导入 `database/init.sql`。

### 构建向量索引

```powershell
cd backend
.\venv\Scripts\flask.exe --app run reindex-knowledge
```

更换 embedding 模型或维度后必须重建索引。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

前端地址 `http://127.0.0.1:5173`，Vite 将 `/api` 代理到后端 5001 端口。

### 运行离线评测

```powershell
# 1. 导出语料快照（只读）
.\venv\Scripts\python.exe -m app.scripts.export_rag_eval_corpus

# 2. 生成 / 更新评测集
.\venv\Scripts\python.exe -m app.scripts.build_curated_rag_eval

# 3. （可选）导出审批清单，人工标记 approved / rejected
.\venv\Scripts\python.exe -m app.scripts.export_eval_review_sheet

# 4. 一键真实链路评测
.\venv\Scripts\python.exe -m app.scripts.run_rag_eval_suite --dataset curated

# 5. 渲染报告
.\venv\Scripts\python.exe -m app.scripts.render_eval_report --tag <tag> --dataset curated --format both
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `venv\Scripts\python.exe run.py` | 启动后端（端口 5001，默认关闭热重载） |
| `venv\Scripts\flask.exe --app run apply-security-migrations` | 应用数据库迁移（幂等） |
| `venv\Scripts\flask.exe --app run reindex-knowledge` | 重建 RAG 向量索引 |
| `venv\Scripts\python.exe -m pytest tests -q` | 运行后端全量测试 |
| `npm --prefix frontend run build` | 前端生产构建 |

## 目录结构

```text
backend/
├── app/
│   ├── routes/                  # Flask 路由（auth / qa / knowledge / admin …）
│   ├── services/
│   │   ├── rag_core/            # RAG v2 核心：执行器、契约、评测器、数据集
│   │   ├── llm/                 # LLM Provider 抽象与选择器
│   │   ├── vector_stores/       # Qdrant / Chroma 向量后端
│   │   ├── text_chunker.py      # 分块器
│   │   └── enhanced_rag_engine.py
│   ├── scripts/                 # 运维与评测脚本（见上文表格）
│   ├── models/                  # SQLAlchemy 模型
│   └── config.py
├── data/                        # 运行时数据（gitignore）
├── tests/                       # pytest 测试
└── venv/

frontend/src/
├── api/                         # API 客户端
├── components/chat/             # 问答组件（引用卡片、不确定性提示等）
├── composables/chat/            # 问答状态管理
└── views/

database/
├── init.sql                     # 开发库初始化
└── migrations/                  # 加性迁移 001 ~ 043
```

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -q
```

测试覆盖 RAG 执行器行为（含引用校验与无据回答分支）、评测数据集完整性、指标计算、发布门禁与各 API 路由。涉及外部服务的测试一律使用 mock 或进程内替代实现，不产生真实网络调用。

## 许可证

- 本项目代码采用 [MIT](LICENSE) 许可证发布。
- 知识库语料中整理自 [HackTricks](https://github.com/HackTricks-wiki/hacktricks) 的内容，版权归原作者 Carlos Polop 所有，遵循其原始许可证（署名—非商业性使用），不随本项目代码以 MIT 授权；如需将语料用于商业场景，请联系原作者获取授权。在此感谢社区贡献者。
