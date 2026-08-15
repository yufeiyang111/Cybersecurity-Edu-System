# CyberGuard Enterprise RAG Core 规格说明

> 状态：**用户已确认设计，按任务分阶段实施**
> 创建日期：2026-08-14
> 范围：公共安全知识库 `knowledge_embeddings` 的企业级检索、证据、评测与交互闭环。
> 非范围：Workspace 私有知识库、实时 Web RAG、多租户向量权限过滤和自主 Agent 改造。

---

## 0. 执行约束

1. 实施必须严格遵循本目录的 `spec.md`、`tasks.md`、`checklist.md`；任何范围、接口、数据模型或验收标准变更，必须先更新三份文档并经用户确认。
2. 代码实施前必须先完成 `tasks.md` 的 T00，记录冻结基线；不得以“感觉效果更好”替代评测证据。
3. 仅使用现有公共知识库：数据库当前有 1,022 条已发布 `KnowledgeItem`，Qdrant `knowledge_embeddings` 当前有 21,650 个点。不得在本项目中新增外部 Web 搜索或自动抓取。
4. 不读取或提交 `backend/.env`、日志、上传文件、运行时文档正文或用户敏感数据；检索 trace 和评测报告必须脱敏、最小化保存。
5. 用户负责管理前后端、Qdrant、Redis 等常驻服务。本实施不得启动、重启或停止这些服务，除非用户在当次任务明确授权。
6. 数据库变更只能使用新的加性迁移，并同步更新 `database/init.sql`；不得 reset、drop、truncate 或重建生产数据。

---

## 1. 背景与已确认基线

### 1.1 当前资产

- 语料源：仓库 `docs/HackTricks/src/`，静态盘点为 993 篇 Markdown；主数据库有 1,022 条已发布公共知识。
- 当前索引：Qdrant `knowledge_embeddings` 为 green；`dense` 为 1,024 维 Cosine 向量，`bm25` 为 IDF sparse 向量，共 21,650 点。
- 当前链路：Markdown/知识条目 → 384 token 分块与 50 token overlap → dense + BM25 → RRF → 可选 cross-encoder rerank → 父块上下文 → LLM 问答。
- 当前质量资产：18 条 `rag_eval_cases`，59 条 `qa_retrieval_logs`。它们不足以成为模型、分块和 Prompt 改动的发布门禁。

### 1.2 当前问题

1. 前端将 dense cosine 乘以 100 显示为“相似度百分比”，但最终排序来自 RRF 或 reranker，该值不是相关概率、更不是回答正确率。
2. 检索链路没有完整 trace：不能解释 dense、BM25、RRF、rerank 和最终上下文选择分别如何影响结果。
3. `QdrantVectorBackend.hybrid_search()` 对同一 sparse query 发出重复词法查询；这是可确认的额外延迟与成本。
4. 召回、重排、上下文选择和生成耦合在 `enhanced_rag_engine.py` 中，无法独立比较不同策略，也无法对每个阶段建立清晰测试。
5. 最终上下文按排序顺序拼接父块，采用字符长度预算；同源内容可能重复，长父块可能挤出更具证据价值的 chunk。
6. 回答只要求笼统标注来源，没有稳定的逐主张 citation ID，也没有服务端验证“回答引用只来自本次授权证据集”。
7. `confidence` 由检索分数启发式线性计算，未经标注数据校准，不能作为用户可理解的“回答可信度”。
8. 评测脚本只测检索文档命中，不测 rerank 后最终证据、上下文覆盖、引用正确性、答案忠实性和拒答行为。

---

## 2. 产品目标与非目标

### 2.1 产品目标

本改造将公共 QA 升级为“带可验证证据的安全知识辅助分析”。系统必须能够：

1. 对每次问答解释检索阶段，不泄露知识正文或用户隐私。
2. 以宽召回、精排和多样性选择构造最小充分 Evidence Pack，而非直接拼接 Top-K 文档。
3. 让最终答案的每项关键事实都能回溯到本次 Evidence Pack 中的固定 citation ID、知识条目、语料版本与行号范围。
4. 在证据不足、证据冲突或检索降级时明确降级，而不是把检索分数伪装成高置信回答。
5. 通过可复现的离线评测和线上匿名化 trace，比对策略版本，形成发布门禁。
6. 在普通聊天体验和研发诊断体验之间建立权限与信息边界：普通用户看答案依据；研发/管理员可看脱敏 trace。

### 2.2 简历可展示成果

完成后项目应可以准确描述为：

> 设计并实现企业级安全知识 RAG Core：基于 Qdrant dense+BM25 hybrid retrieval、可插拔 cross-encoder rerank、证据包构建与逐主张引用校验；建设 200+ 条分层评测集，覆盖 Recall/nDCG/citation completeness/faithfulness 与注入负例；通过策略版本、检索 trace、灰度开关和回归门禁实现可观测、可评测的 RAG 发布流程。

上述描述必须在代码、测试、评测报告与演示界面中有对应证据，不能只写在简历中。

### 2.3 明确非目标

- 不接入通用搜索引擎、网页爬取、浏览器自动化或实时外网内容。
- 不重建 Workspace 私有知识库；`security_knowledge_embeddings` 仍不属于本期。
- 不改变扫描器、Agent Loop、修复建议或既有 LLM Provider 契约。
- 允许向所属用户展示并按既有 `qa_records.reasoning` 范围保存 Provider 原样返回的 CoT；它仅是模型输出，不是证据、事实、置信度或审计结论。Trace、评测、指标和日志不得复制或保存该内容。
- 不承诺模型回答可替代人工安全决策。

---

## 3. 术语与不变量

### 3.1 术语

| 术语 | 定义 |
| --- | --- |
| Candidate | dense 或 BM25 阶段召回的原始 chunk，尚未证明适合给模型。 |
| Retrieval Trace | 本次请求各检索阶段的脱敏排序、数量、耗时、策略版本和降级状态。 |
| Evidence Reference | 有稳定 ID 的最小可引用证据，绑定 knowledge item、chunk、语料版本、标题路径与行号。 |
| Evidence Pack | 经过重排、去重、多样性选择和 token 预算装配后，允许进入生成 Prompt 的证据集合。 |
| Citation Manifest | 最终回答中所有 citation ID 与 Evidence Reference 的可验证映射。 |
| Answer Status | `supported`、`insufficient_evidence`、`conflicting_evidence`、`degraded` 之一。 |
| Pipeline Version | 检索参数、算法与 Prompt 模板的不可变版本标识，用于比对和回滚。 |

### 3.2 不变量

1. 任何 Evidence Reference 都必须来自本次经过权限与注入检查的 Evidence Pack；不得由模型虚构 citation ID。
2. 任何 `supported` 的关键主张至少包含一个有效 citation；没有有效 citation 的关键主张不得标记为 supported。
3. 文档正文、完整用户问题、原始 Prompt、原始 CoT、凭据和 Token 不得出现在 trace、指标或日志中；唯一允许的 CoT 保存位置是当前用户有权读取的既有 `qa_records.reasoning` 字段。
4. dense cosine、BM25、RRF、rerank 分数均只能视为检索特征；不得在 UI 中直接解释为事实正确率或回答置信度。
5. 当前默认链路必须可通过 Feature Flag 切换回 legacy 行为；新链路出错时安全降级为 legacy retrieval 或明确返回 degraded，不得静默返回伪造引用。
6. 所有新增数据库表、字段和迁移必须是加性的，旧 QA 记录和旧客户端继续可读。

---

## 4. 目标架构

```text
QA Route
  │
  ├─ Legacy adapter（兼容现有 ask / ask_stream）
  │
  └─ EnterpriseRagPipeline.execute(request)
       │
       ├─ QueryNormalizer（确定性规范化，保留原问题）
       ├─ CandidateRetriever（Qdrant dense + BM25 + RRF）
       ├─ RerankStage（现有 reranker adapter，可降级）
       ├─ EvidencePackBuilder（去重、多样性、token 预算、父子窗口）
       ├─ CitationManifestBuilder（稳定 citation ID 与可追溯元数据）
       ├─ AnswerComposer（稳定系统提示 + Evidence Pack + 结构化回答契约）
       ├─ CitationValidator（引用存在性、授权范围、行号、状态校验）
       └─ RetrievalTraceRecorder（脱敏 trace、策略版本、耗时）
```

### 4.1 深模块与接口

新增 `backend/app/services/rag_core/`，作为本期唯一的主 seam。调用方只需要理解下列接口：

```text
EnterpriseRagPipeline.execute(request) -> RagExecutionResult
EnterpriseRagPipeline.stream(request) -> Iterator[RagStreamEvent]
RagEvaluator.run(evaluation_run_request) -> RagEvaluationReport
```

模块内部可以有多个小实现，但 Route、前端和评测工具不得直接依赖 Qdrant 细节、RRF 公式、父块拼接规则或 citation 编码规则。

### 4.2 请求和结果契约

`RagExecutionRequest` 必须包含：

- `query`：原始用户问题；
- `conversation_history`：已清洗的有限窗口；
- `user_id`、`record_id`、`request_id`：审计关联；
- `mode`：`user` 或 `diagnostic`；
- `pipeline_version`：可选显式版本，否则使用 Feature Flag 当前默认值。

`RagExecutionResult` 必须包含：

- `answer`；
- `answer_status`；
- `citations`：面向客户端的、无正文泄露的 citation 摘要；
- `evidence_manifest`：仅用于持久化/诊断的结构化映射；
- `trace_id`；
- `retrieval_summary`：候选、重排、证据数量和降级状态；
- `warnings`；
- `model/provider/usage/latency`。

### 4.3 策略配置与版本

配置必须有安全默认值、严格范围校验和稳定指纹。第一版提供：

| 配置 | 默认值 | 说明 |
| --- | ---: | --- |
| `RAG_PIPELINE_V2_ENABLED` | `false` | 新链路 Feature Flag。 |
| `RAG_CANDIDATE_TOP_K` | `40` | RRF 后供精排的最大候选数，范围 10–100。 |
| `RAG_RERANK_TOP_K` | `15` | 供 Evidence Pack 选择的重排结果数，范围 3–30。 |
| `RAG_EVIDENCE_TOP_K` | `6` | 最终证据数量，范围 2–10。 |
| `RAG_EVIDENCE_TOKEN_BUDGET` | `3500` | 使用 tokenizer 计数的 Evidence Pack 预算。 |
| `RAG_DIAGNOSTICS_ENABLED` | `false` | 是否允许授权诊断 API 返回脱敏 trace。 |
| `RAG_STRICT_CITATIONS_ENABLED` | `false` | 是否强制关键主张必须有有效 citation。 |

`pipeline_version` 由算法版本、Embedding 版本、reranker 版本、Prompt 模板版本和上述配置指纹生成；不得含用户信息或随机值。

---

## 5. 检索与证据设计

### 5.1 QueryNormalizer

第一期只做确定性、可审计的规范化：空白规范、Unicode 规范、保留原 query、提取高价值标识符（CVE/CWE、协议端口、配置键、函数/类名）。

不得在第一期引入 LLM query rewrite、HyDE 或多查询扩展；这些功能只有在评测证明当前链路对特定类别存在系统性低召回时才进入后续规格。

### 5.2 CandidateRetriever

- 复用 Qdrant dense + BM25 与 RRF，修复重复 lexical 请求。
- 每个 candidate 必须记录来源阶段、dense rank/score（如有）、BM25 rank（如有）、RRF score、原始 chunk ID、文档 ID、标题路径、行号和 embedding/corpus version。
- 返回的 `similarity` 保持向后兼容，但不再作为 UI 的百分比含义；新增明确命名的阶段特征。
- 所有分数必须可为空，代码不得假定 dense、BM25 与 rerank 分数处于同一尺度。

### 5.3 RerankStage

- 使用现有 API/local reranker adapter；未配置、超时或失败时保留 RRF 顺序并在 trace 中写入 `rerank_status=skipped|failed`。
- 不允许 embedding 余弦伪重排覆盖真实 reranker 结果；降级策略必须可观测。
- Rerank 输入使用 child chunk；Evidence Pack 可在后续展开受限 parent window。

### 5.4 EvidencePackBuilder

输入：已重排 candidates 与 token budget。输出：按 citation ID 排序的 Evidence Pack。

选择规则：

1. 先过滤注入命中、缺正文、缺 document/chunk 标识、版本不一致和重复 chunk。
2. 同文档相邻 chunks 可合并为连续行窗口；非相邻 chunks 不能伪造连续引用。
3. 同一知识条目默认最多占 Evidence Pack 的 40%，除非候选集中只有一个可用来源。
4. 优先保留与 query 标识符、标题路径、rerank 结果一致的 chunk；相同相似内容只保留一份。
5. 预算以 embedding tokenizer 真实 token 数计算，不能再以 Python 字符数作为主预算。
6. 若没有能够支撑关键主张的安全证据，产生 `insufficient_evidence` 候选状态，不用低相关内容强行凑齐。

### 5.5 Citation Manifest

Citation ID 格式：`C{ordinal}-{knowledge_item_id}-{chunk_id_hash}-{corpus_version_short}`。

每条引用必须包含：

- citation ID；
- knowledge item ID；
- title；
- title path；
- relative source path；
- corpus version；
- chunk ID；
- start/end line；
- 受限的证据摘要；
- 注入检查状态。

用户侧不显示 RRF、dense cosine 或完整 parent_text；诊断侧可显示脱敏阶段排名。

---

## 6. 生成、答案状态与验证

### 6.1 Prompt 契约

系统提示保持稳定前缀，Evidence Pack 位于明确标记为不可信资料的数据区。模型必须输出：

```text
<answer_status>supported | insufficient_evidence | conflicting_evidence | degraded</answer_status>
<answer>面向用户的 Markdown 答案</answer>
<claims>
  <claim citations="C1-...,C2-...">关键事实或结论</claim>
</claims>
<uncertainties>证据不足、冲突或适用条件</uncertainties>
```

Prompt 不得强迫模型生成 CoT。若 Provider 原生返回 reasoning，则允许向当前记录所属用户原样显示和保存；该内容必须与“回答依据”区分，且不得被 CitationValidator 当作证据或事实来源。

### 6.2 CitationValidator

生成后必须验证：

1. 所有 citation ID 存在于本次 Evidence Pack；
2. citation 不跨用户、知识范围或 corpus version；
3. `supported` 答案的每个关键 claim 至少有一个有效 citation；
4. 引用格式错误、引用不存在或引用全部被剔除时，将答案降级为 `degraded`，并提示用户重新提问或查看不足说明；
5. 验证器不对自然语言“真伪”作伪确定性判断；忠实性由离线评测和人工抽样共同评估。

### 6.3 用户可见状态

| 状态 | 用户文案语义 | 允许的回答行为 |
| --- | --- | --- |
| `supported` | 已找到可追溯资料 | 正常回答，显示引用。 |
| `insufficient_evidence` | 当前知识库没有足够依据 | 说明缺什么信息，不编造事实。 |
| `conflicting_evidence` | 检索到相互冲突资料 | 罗列差异、版本或适用条件，不强行裁决。 |
| `degraded` | 检索/重排/引用校验发生降级 | 明确未验证范围，不能显示虚假高置信。 |

---

## 7. 数据模型与 API

### 7.1 新增迁移

新增 `database/migrations/038_enterprise_rag_core.sql`，在 `backend/app/scripts/apply_sql_migration.py` 的 `MIGRATION_IDS` 中按序注册，并同步 `database/init.sql`。

新增表：

1. `rag_pipeline_versions`
   - `id`、`version_key`（唯一）、`config_json`、`prompt_version`、`embedding_version`、`reranker_version`、`created_at`。
2. `rag_retrieval_traces`
   - `id`、`request_id`、`record_id`、`user_id`、`pipeline_version_id`、`query_fingerprint`、`stage_summary_json`、`warnings_json`、`retrieval_ms`、`created_at`。
   - 不保存原 query、原文 chunk、Prompt 或 CoT。
3. `rag_evaluation_runs`
   - `id`、`pipeline_version_id`、`corpus_version`、`status`、`metrics_json`、`report_path`、`started_at`、`finished_at`。
4. `rag_evaluation_results`
   - `id`、`run_id`、`case_id`、`retrieval_metrics_json`、`citation_metrics_json`、`answer_metrics_json`、`failure_stage`、`notes`。

对现有表的加性扩展：

- `qa_records`：增加 `answer_status`、`citation_manifest_json`、`rag_trace_id`、`pipeline_version_key`。
- `rag_eval_cases`：增加 `expected_evidence_json`、`expected_status`、`difficulty`、`is_active`、`updated_at`。

### 7.2 API

保留既有 `/api/qa/ask` 与 `/api/qa/ask/stream` 返回字段；增加：

- `answer_status`
- `citations`
- `retrieval_summary`
- `trace_id`
- `pipeline_version`

现有只读授权接口按兼容方式扩展：

- `GET /api/qa/records/<record_id>/evidence`：仅该 record 所属用户可读取。保留既有 `citations` manifest 和计数；新增受控 `citation_details` 与顶层 `retrieval_signal`；每项 citation detail 只包含稳定 `citation_id`、标题/路径、起止行号、关联主张数、限长纯文本预览和后端解析出的公共知识库跳转目标，`retrieval_signal` 只含高/中/低/暂不可用等级及“非正确率”语义。
  - 跳转目标仅支持当前公共知识库的已发布 `KnowledgeItem`，格式为 `document: { type: "public_knowledge", knowledge_id: <int> }`；前端只能使用这个经 record + citation_id 校验后的字段导航，不能从 legacy `sources`、`doc_id`、标题或 URL 猜测文档 ID。
  - 预览从 citation 记录的行号范围裁剪，必须去除 HTML、限制字符数并标记是否截断；不返回完整文档、完整 query、Prompt、CoT、原始 rerank 分数或内部 trace。
  - 不存在 record、非所有者、citation 不属于该 record、文档已删除/未发布或 manifest 非法时，返回安全错误或不可导航状态；不得降级为任意 `knowledge_id` 查询。
- `GET /api/admin/rag/traces/<trace_id>`：仅管理员，返回脱敏 trace。
- `GET /api/admin/rag/evaluation-runs`：仅管理员分页查看评测运行摘要。
- `GET /api/admin/rag/evaluation-runs/<run_id>`：仅管理员查看按类别、阶段和策略版本拆分的指标。

`confidence` 当前来自未校准的检索启发式，不能作为“回答正确率”或“回答置信度”显示。用户界面只能将其映射为 `检索辅助信号：高 / 中 / 低 / 暂不可用`，并明确说明它不是准确率概率；用户结论以 `answer_status`、citation validity、主张覆盖数和证据数量为准。

所有新增或扩展接口必须验证身份、对象归属和管理员角色；不得依赖前端隐藏按钮做鉴权。

---

## 8. 前端设计

### 8.1 用户聊天视图：可核验证据卡

在现有 `/qa` 聊天视图中新增、复用并拆分：

- `AnswerEvidenceSummary.vue`：展示 `answer_status`、稳定 citation 数、主张覆盖数与“查看证据”入口；流式完成前显示证据处理中，旧记录显示兼容说明。
- `AnswerCitationList.vue`：按 `[C#]` 展示标题、标题路径、行号、证据状态和受限预览；每项可聚焦、可通过 Enter/Space 打开详情或原文。
- `LegacySourceList.vue`：仅展示旧记录已保存的标题、来源与行号；不渲染正文、不展示相似度、不支持详情、预览或原文跳转。
- `CitationDetailDrawer.vue`：只接收页面/composable 提供的详情状态和数据，展示受控预览、行号、关联主张数、检索辅助信号和“在知识库中阅读全文”；组件内不得请求 API。
- `AnswerUncertaintyPanel.vue`：仅在 `insufficient_evidence`、`conflicting_evidence`、`degraded` 时展示可执行的下一步建议。
- `useCitationEvidence.js`：唯一负责调用 owner-scoped evidence API、缓存同一 record 的详情、处理 loading/error/legacy 状态，并在后端返回合法 `document` 目标后导航到 `/knowledge/:id`。
- `citationPresentation.js`：纯函数归一化 citation manifest、状态文案、主张覆盖和未校准检索辅助信号；不得输出 cosine/rerank 百分比。

交互与安全要求：

1. 新回答 SSE 完成时先稳定显示正文和 answer status；`citations` 缺失、格式非法、断流或 error 发生在正文之后时，将消息显式标记为 `degraded`，不得静默隐藏来源区。
2. 点击 citation 标识或标题打开详情；点击“查看原文/阅读全文”时只能使用 `useCitationEvidence` 已解析的 `document.knowledge_id` 导航。无 `pipeline_version` 的旧记录若保存了 `sources`，必须显示只读历史来源卡（标题、来源、行号）；不得显示相似度、正文、`document_id`，也不得再直接调用 `knowledgeAPI.getKnowledge(source.id)` 或猜测跳转目标。
3. 预览是后端受限返回的阅读辅助，不是模型上下文或原始 Evidence Pack；必须显示来源、行号和截断语义，不能渲染未消毒 HTML。
4. 不显示“dense cosine × 100”的相似度，也不把未校准 `confidence` 标成回答置信度；若存在则显示“检索辅助信号（非正确率）”等级，否则显示“暂不可用”。
5. 证据状态优先级高于任何辅助信号：`supported`、`insufficient_evidence`、`conflicting_evidence`、`degraded` 必须有明确用户文案和下一步操作。
6. 证据卡、抽屉、焦点轮廓、空态与错误态必须遵循既有 QA 页面 `--chat-*` token、内容宽度、圆角和暗色主题；不得混入 Security Workbench 的蓝色卡片风格或新增全局样式。聊天组件优先复用 `BaseIcon`，管理员页面使用完整 `BasePanel`、`BaseBadge`、`BaseButton` 组件库。
7. 桌面端引用列表保持与聊天正文同宽；平板端抽屉缩窄；手机端卡片保留 `[C#]`、标题、状态、行号和“查看原文”，预览与详情置入全宽抽屉。所有可点击 citation 均有语义标签、键盘操作和焦点恢复。

### 8.2 管理/诊断视图

新增管理员路由 `/admin/rag-diagnostics`，继承现有 `/admin` 的前端 role guard，并继续以后台 API 的管理员鉴权为最终安全边界。页面只负责编排，细分为 `components/admin/ragDiagnostics/` 组件，使用 `BasePanel`、`BaseBadge`、`BaseButton`，并展示 loading/empty/error/success 骨架状态。

受控展示字段：

```text
pipeline version
候选数量（dense / BM25 / RRF）
rerank 是否执行与耗时
Evidence Pack 数量 / token 数
注入剔除数量
最终 answer status
各阶段耗时
warning 与评测摘要
```

不得展示完整用户问题、完整资料正文、Token 明细、Prompt、CoT、document ID、citation ID、用户 ID 或 report path。

---
## 9. 评测与质量门禁

### 9.1 评测集

扩展 `rag_eval_cases` 至至少 200 条活跃 case，类别至少包括：

- `concept`：安全概念解释；
- `identifier`：CVE/CWE、端口、配置键、函数名；
- `defense`：检测、修复、加固；
- `multihop`：多资料综合；
- `alias`：中英文别名与缩写；
- `insufficient`：语料中没有答案；
- `conflict`：版本或适用条件冲突；
- `injection`：恶意文档/查询提示词注入负例。

每个 case 必须有 expected document/chunk evidence、预期 answer status 和人工审核说明；`expected_answer` 可作为参考，不作为单一自动正确性标准。

评测标签以受版本控制的 `backend/rag_eval_cases.jsonl` 为唯一人工可审阅来源；每条至少包含稳定 `case_key`、query、类别、难度、expected evidence、expected status 与审核说明。该文件不得保存文档正文或完整 Prompt；`database/seed_rag_eval_cases.sql` 仅由它转换出的最小字段生成，并按 query 幂等导入。

### 9.2 指标

| 阶段 | 必测指标 |
| --- | --- |
| Candidate | Recall@20、Recall@40、MRR@20、nDCG@10。 |
| Rerank | nDCG@10、MRR@10、与 RRF baseline 的胜负样本。 |
| Evidence Pack | context precision、context recall、来源多样性、token 预算占用。 |
| Answer | citation correctness、citation completeness、人工忠实性抽样、拒答正确率。 |
| Runtime | retrieval p50/p95、rerank p50/p95、降级率、失败率。 |

### 9.3 发布门禁

新 Pipeline Version 只有同时满足以下条件才可默认启用：

1. 所有自动化测试通过，外部 embedding/rerank/LLM 全部 mock；
2. 对冻结评测集，Recall@20、nDCG@10、citation completeness 不低于 legacy baseline；
3. 至少两个主要质量指标优于 baseline，且没有任何高风险类别下降；
4. `insufficient` 和 `injection` 类别没有把不支持的答案标成 supported；
5. 检索 p95 不高于 legacy 的 1.25 倍，或性能代价有经用户确认的收益证据；
6. 人工抽检 30 条 supported 答案，关键主张 citation correctness 至少 90%，且不存在 P0 级越权/伪造引用；
7. 可以通过 Feature Flag 在一次配置变更内回退到 legacy。

---


### 9.4 Release gate verifier

`backend/app/scripts/rag_release_gate.py` compares one persisted, sanitized legacy
report with one persisted, sanitized V2 report. It is a local offline command: it
must not create a Flask application, call a provider, access a database, or read
source documents. The verifier accepts only report files in `backend/` whose names
match `rag_report_<safe-name>.json`; its optional result file must match
`rag_release_gate_<safe-name>.json` and is not committed.

The verifier treats a pair as comparable only when both reports use
`enterprise-rag-eval-v1`, the expected pipelines (`legacy` and `v2`), the same
safe corpus version, an equal case count of at least 200, and the same outcome
case-id set. Unknown report fields are ignored. The release-gate output never
includes queries, case ids, titles, notes, prompts, document text, raw exceptions,
or arbitrary report blocker text.

Automated blocking checks are:

1. either source report has release blockers, a malformed required field, or the
   reports are not comparable;
2. `retrieval.recall_at_20`, `retrieval.ndcg_at_10`, or
   `evidence.expected_evidence_coverage` regresses from legacy;
3. the V2 `insufficient` or `injection` category reports a non-zero
   `unsafe_supported_negative_count`;
4. V2 retrieval p95 is greater than legacy p95 multiplied by 1.25. A zero legacy
   p95 requires a zero V2 p95.

A report pair with no automated blocker must improve at least two of
`retrieval.recall_at_20`, `retrieval.ndcg_at_10`,
`evidence.expected_evidence_coverage`, and `evidence.context_precision` to be
`READY_FOR_CANARY`. Fewer improvements produces `NEEDS_REVIEW`; any failed
blocking check produces `BLOCKED`.

`READY_FOR_CANARY` is only an automated comparison result. It does not replace the
30-answer citation audit, the P0 security review, a user-managed Feature Flag
rollback rehearsal, or the final release decision. Citation completeness remains a
manual audit requirement until both pipelines expose a comparable automatic metric.

Example command (run from `backend/` with user-generated reports):

```powershell
venv\Scripts\python.exe -m app.scripts.rag_release_gate `
  --legacy-report rag_report_<legacy>.json `
  --v2-report rag_report_<v2>.json `
  --output-name rag_release_gate_<comparison>.json
```


For local browser smoke verification, V2 and strict citations may be enabled only
for the test process. The test must verify evidence status, a server-authorized
preview, and an original-document route for one supported answer, plus
insufficient-evidence and prompt-injection negative cases. Unless the release gate
and manual audit are complete, the process must be returned to legacy mode after
the test.

Exit code `0` means `READY_FOR_CANARY`, `2` means `NEEDS_REVIEW`, and `3` means
`BLOCKED`.

## 10. 安全、隐私与可观测性

1. 所有 Evidence Pack 内容视为不可信资料；延续并扩大 prompt injection 检测范围。
2. 历史记录、用户偏好、记忆、附件必须显式标注来源类型，不能伪装为系统指令或可信证据。
3. Trace 保存 ID、rank、分数、耗时和摘要哈希；不保存文本正文。
4. 评测报告保存至已忽略的 `backend/rag_report_*.json`，数据库仅保存摘要、版本和受控路径。
5. 回答、trace、评测运行通过 request ID、record ID 和 pipeline version 关联，便于排障与审计。
6. 日志不得使用 `print` 输出异常正文；使用结构化 logger，记录 error type、stage、trace ID 与安全摘要。



### 10.4 MySQL migration compatibility

The public RAG schema uses `BIGINT UNSIGNED` for `rag_eval_cases.id`; every
foreign-key column targeting it, including `rag_evaluation_results.case_id`, must
use the same type. `database/init.sql`, the additive migration, and the SQLAlchemy
ORM contract must remain synchronized.

The migration runner must support MySQL versions that do not accept `ADD COLUMN IF
NOT EXISTS`. For only those statements, it executes standard `ADD COLUMN` and
suppresses only MySQL error code `1060` (duplicate column). Any other database
error must still fail the migration and must never be hidden. This preserves an
idempotent, additive recovery path for a partially applied local development
migration.

### 10.1 Runtime metric contract and rollback

1. `RagRuntimeMetrics` is a thread-safe, worker-local in-process registry. Its returned `scope` must be `process`; it must never be described as an aggregate for multiple Flask workers, hosts, or deployments.
2. Allowed metric dimensions are the fixed pipeline mode, validated pipeline version, answer status, fixed component name, and fixed failure/degradation outcome. The registry must reject or collapse unknown values. Query text, title, user ID, document ID, citation ID, request ID, prompt, evidence text, raw provider error, and exception message are forbidden from metric labels and snapshots.
3. Only the bounded stage names `candidate`, `rerank`, `evidence`, `generation`, `answer`, and `retrieval_total` may store integer milliseconds. Each stage keeps at most `RAG_METRICS_SAMPLE_LIMIT` samples (16--5000), and the registry keeps at most 24 series. Percentiles are therefore operational signals, not a durable analytics database.
4. The V2 executor records per-stage timing and its final answer/degradation outcome. Trace persistence failures record the fixed `trace_db/failed` component event without affecting the already generated answer. Legacy is a rollback target and offline baseline; T09 must measure live legacy/V2 latency before any performance claim is made.
5. `GET /api/admin/rag/runtime-metrics` is admin-only. It is available only when `RAG_DIAGNOSTICS_ENABLED=true`; otherwise it returns 404 after authorization. It returns the effective non-sensitive runtime flag snapshot and controlled aggregate metrics only.
6. Flag values are validated from startup configuration. There is no mutable flag-management API. To rollback, set `RAG_PIPELINE_V2_ENABLED=false`, have the user restart the backend, confirm the effective mode is `legacy`, and rerun a prepared smoke case. This changes no schema and requires no database rollback, reset, truncate, or reindex.
7. Automated failure injection must cover Qdrant, reranker, LLM, citation validator, and trace database write failures. The tests must verify both safe user behavior and that metric payloads omit raw query/error details.

---

## 11. 交付定义

本规格完成不等于“代码写完”。只有以下全部成立才算完成：

- 200+ 冻结评测 case 已入库、类别分布可查询；
- legacy 和 v2 能对同一 case 生成可对比报告；
- v2 按门禁优于或不劣于 legacy；
- 用户能查看答案状态、citation、行号和证据不足说明；
- 管理员能查看脱敏 trace 和评测运行；
- 新增 schema、API、Feature Flag、迁移、回滚和测试都有验证证据；
- `tasks.md` 和 `checklist.md` 中所有 blocker 项完成并登记结果。

### 10.5 引用语义与首页问答入口

1. `supported` 状态的 citation 才能标记为“可核验引用”或“已验证引用”，并可展示主张覆盖数。
2. `insufficient_evidence` 状态下，即使存在检索结果，也必须标记为“相关参考资料”，明确其仅供继续阅读、未作为当前回答结论的支撑依据，并隐藏主张覆盖数。
3. `conflicting_evidence` 与降级状态不得伪装成结论依据；分别展示“冲突参考资料”与“待核验资料”。
4. 首页在首屏稳定后预加载 QA 路由 chunk；预加载失败不可阻断实际路由跳转，且失败后允许再次尝试。首页卸载时必须取消尚未执行的预加载定时器。

### 10.6 流式回答、可展示推理与阅读位置

1. SSE 只能展示 Provider 实际返回的 `reasoning` 字段；不得把检索摘要、模型名、耗时、引用数量或服务端内部提示词伪装成模型 CoT。若 Provider 未提供该字段，前端不得显示“已思考”或虚构的推理内容。
2. 当前记录可以展示受控的“检索与生成过程”作为透明度补充，但只允许呈现白名单阶段与聚合值：候选召回数、重排输出数、可用证据数和回答生成完成状态。严禁传递或渲染 query、改写 query、知识库正文、候选正文、Prompt、Provider 异常正文或其他任意 trace 字段。
3. V2 在没有底层 token streamer 时，必须先完成回答与 Citation 校验，再依次发送实际 `reasoning`（如有）、已校验的 answer `delta` 和 `done`。这不是未校验 token 的实时透传；其安全目标是避免用户在校验前看到不可信引用。
4. 新发送问题、首次打开会话、切换会话时，消息容器强制定位到底部。流式期间，容器距底部不超过 56px 时自动跟随；用户向上滚动离开阈值后立即停止自动滚动，只有手动回到底部阈值内才恢复。向上加载历史记录必须保留用户阅读位置。
5. 引用卡片只显示短序号 `C-1`、`C-2` 等，原始 citation 标识仅保留在 `title` 与无障碍标签中。卡片使用 `minmax(0, 1fr)` 和固定短序号列，任何长标识不得撑破布局。