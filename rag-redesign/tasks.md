# CyberGuard Enterprise RAG Core 执行任务书

> 依赖文档：`rag-redesign/spec.md`、`rag-redesign/checklist.md`
> 状态标记：`[ ] 未开始`、`[-] 进行中`、`[x] 已完成`、`[!] 阻塞`。
> 规则：每个任务完成后必须先更新本文件和 `checklist.md` 的证据，再开始后续任务；不得跨过依赖直接实施。

---

## 0. 任务依赖图

```text
T00 基线与安全边界
 ├─ T01 契约、配置与迁移
 │   ├─ T02 Qdrant trace 与 candidate 检索
 │   ├─ T03 Rerank 与 Evidence Pack
 │   │   └─ T04 Citation Manifest、Prompt 与验证器
 │   ├─ T05 持久化 trace、QA API 与兼容
 │   └─ T06 离线评测与报告
 ├─ T07 前端证据体验与诊断
 ├─ T08 可观测性、权限和回滚
 └─ T09 全链路验收、灰度与项目叙事
```

T02、T03、T04、T05、T06 的业务实现必须建立在 T01 的稳定契约上；T07 不得在 API 契约冻结前开始。

---

## T00 基线、数据边界与可复现报告

**状态：** `[x]`

**目的：** 在不改检索策略前冻结当前质量、性能和数据边界，作为所有后续改动的对照。

**文件范围：**

- `backend/app/scripts/rag_evaluate.py`
- `backend/tests/test_qa_retrieval_eval.py`
- `database/seed_rag_eval_cases.sql`
- `rag-redesign/checklist.md`

**工作项：**

- [x] 确认 `backend/venv/Scripts/python.exe` 存在；不使用系统 Python。
- [x] 只读记录公共库 aggregate：已发布 KnowledgeItem 数、Qdrant `knowledge_embeddings` 点数、dense/sparse 配置、当前评测 case 数。
- [x] 修复并验证 CI workflow 的后端步骤 YAML 结构，使 compile 与 pytest 都是独立有效 step；不得降低测试范围。
- [x] 运行 legacy 检索评测并保存带日期与 pipeline version 的忽略报告；不得读取或写出文档正文。
- [x] 审计 18 条现有 case 的数量、现有字段与评测覆盖缺口；正式补齐类别、有效性、预期 evidence、预期 answer status 并清理无效 case 的数据变更移至 T06（依赖 T01 schema）。
- [x] 记录 legacy 的 Recall@1/3/5、MRR、候选数、context 字符数、retrieval 时间；明确哪些指标暂不可得。
- [x] 将基线数值、命令、环境版本和限制登记到 `checklist.md` 的证据表。

**已登记证据（2026-08-14）：**

- 只读 aggregate：1,022 条已发布 KnowledgeItem；Qdrant `knowledge_embeddings` 为 21,650 点（dense 1,024 Cosine + BM25 sparse）。
- legacy retrieval baseline：18 case，Hit@1=0.4444、Hit@3=1.0000、Hit@5=1.0000、MRR=0.7037。
- 脱敏报告：`backend/rag_report_20260814_legacy_baseline.json`（gitignore，不含 query/正文）。
- CI YAML：backend compile 与 pytest 为独立有效步骤，使用 venv 中 PyYAML 解析校验。

**完成条件：**

- 有一份可复跑的 legacy baseline 报告；
- 评测脚本的输入、输出和限制由测试覆盖；
- CI 后端测试步骤语义正确；
- 不提交评测产物、日志、数据库导出或敏感数据。

---

## T01 RAG Core 契约、配置、加性迁移与兼容层

**状态：** `[x]`
**依赖：** T00

**文件范围：**

- `backend/app/services/rag_core/__init__.py`
- `backend/app/services/rag_core/contracts.py`
- `backend/app/services/rag_core/pipeline.py`
- `backend/app/services/enhanced_rag_engine.py`（仅增加 v2 委托入口）
- `backend/app/config.py`
- `backend/app/models/qa.py`
- `backend/app/models/__init__.py`
- `backend/app/scripts/apply_sql_migration.py`
- `database/migrations/038_enterprise_rag_core.sql`
- `database/init.sql`
- `backend/tests/test_rag_core_contracts.py`
- `backend/tests/test_rag_core_migration_contract.py`
- `backend/tests/test_agent_loop_migration_registry.py`
- `backend/tests/test_remediation_models.py`（迁移序列基线同步）

**工作项：**

- [x] 新建 `rag_core` 深模块，定义 `RagExecutionRequest`、`RagExecutionResult`、`Candidate`、`EvidenceReference`、`EvidencePack`、`RetrievalTrace`、`CitationManifest` 和 `AnswerStatus` 判别联合类型。
- [x] 明确 legacy adapter：现有 `EnhancedRAGEngine.ask/ask_stream` 在 v2 Feature Flag 关闭时行为不变；打开后委托 `EnterpriseRagPipeline`。
- [x] 增加 `RAG_PIPELINE_V2_ENABLED`、候选数、rerank 数、evidence 数、token budget、诊断和严格引用开关；为非法配置写单元测试。
- [x] 实现无用户数据的 `pipeline_version` 指纹生成；测试相同配置稳定、配置/模型变化后变化。
- [x] 新增 038 加性迁移及 `init.sql`：pipeline version、trace、evaluation run/result 表，以及 `qa_records` 和 `rag_eval_cases` 的加性字段。
- [x] 迁移必须幂等；测试 migration runner 的脚本列表已包含 038，且不得改写历史迁移。
- [x] 保持旧 QA 记录反序列化兼容：新字段为空时仍按 legacy sources/answer 展示。

**已登记证据（2026-08-14）：**

- 新增 RAG Core 契约、配置指纹、Feature Flag 兼容 adapter 与 038 加性 schema；默认 `RAG_PIPELINE_V2_ENABLED=false`。
- 聚焦验证：`29 passed`（契约/迁移/旧 QA），旧 RAG/QA 回归：`56 passed`，最终后端全量回归：`1180 passed, 1 skipped`（2026-08-14）。
- migration runner 使用 fake 空 registry 覆盖首次应用、038 执行及重复跳过；旧 QA 空新字段序列化有单测。
- 未执行任何真实数据库迁移、reset、drop 或 truncate；运行时 schema 应用留待用户确认本地开发库后执行。
**完成条件：**

- 新模块接口可被测试 fake 使用；
- 038 migration、migration runner 与 `init.sql` 同步；
- Feature Flag 默认关闭；
- 旧 QA/RAG 测试通过。

---

## T02 Candidate Retriever、Qdrant Hybrid Trace 与重复查询修复

**状态：** `[x]`
**依赖：** T01

**文件范围：**

- `backend/app/services/vector_stores/contracts.py`
- `backend/app/services/vector_stores/qdrant.py`
- `backend/app/services/rag_core/candidate_retriever.py`
- `backend/tests/test_qdrant_hybrid_trace.py`
- `backend/tests/test_rag_candidate_retriever.py`

**工作项：**

- [x] 为向量命中增加阶段元数据契约：dense rank/score、BM25 rank、RRF score、来源阶段；不得滥用 `similarity` 字段承载不同尺度的值。
- [x] 删除 `hybrid_search()` 中重复的 sparse `query_points` 调用；测试单次 hybrid 请求只触发一次 dense 和一次 BM25 查询。
- [x] 将 RRF 逻辑封装在 Qdrant adapter 内，返回候选 trace 所需的脱敏元数据；Route 和 UI 不感知 Qdrant 实现细节。
- [x] `CandidateRetriever` 使用 Qdrant adapter，执行 deterministic QueryNormalizer 后生成最大 `RAG_CANDIDATE_TOP_K` candidates。
- [x] 记录 dense-only、BM25-only、both 三种命中来源，以及 embedding 降级时的 lexical-only 状态。
- [x] 对 CVE/CWE、端口、配置键、中英文混合、空 query、embedding 降级、Qdrant 异常分别写单元测试。

**已登记证据（2026-08-14）：**

- Qdrant hybrid 检索每次仅执行一次 dense 与一次 BM25 查询；RRF 结果以独立 `retrieval_metadata` 暴露阶段 score、rank 与来源路径。
- 新增确定性 `QueryNormalizer` / `CandidateRetriever`，候选上限遵循 `RAG_CANDIDATE_TOP_K`，trace 不含正文。
- 测试：聚焦 `21 passed`；后端全量 `1184 passed, 1 skipped`；端口误识别修正后聚焦 `4 passed`。

**完成条件：**

- 旧 VectorHit 兼容；
- 新 candidate trace 可序列化且不包含正文；
- 重复 lexical 查询有回归测试；
- Qdrant 异常不导致伪造分数或伪造 citation。

---

## T03 Rerank Stage 与 Evidence Pack Builder

**状态：** `[x]`
**依赖：** T02

**文件范围：**

- `backend/app/services/rag_core/rerank_stage.py`
- `backend/app/services/rag_core/evidence_pack_builder.py`
- `backend/app/services/rag_core/evidence_policy.py`
- `backend/app/services/text_chunker.py`（补充 token 计数模式接口）
- `backend/tests/test_rag_rerank_stage.py`
- `backend/tests/test_evidence_pack_builder.py`
- `backend/tests/test_text_chunker.py`

**工作项：**

- [x] 以 adapter 方式复用现有 `app.services.llm.reranker_service`，不复制 Provider 调用代码。
- [x] 记录 rerank `applied/skipped/failed`、输入数、输出数、耗时和失败类型；不记录 query/文档正文。
- [x] 当 reranker 不可用时保持 RRF 顺序，不能使用不可靠的伪分数把结果包装成 rerank 成功。
- [x] Evidence Pack 使用 tokenizer token budget，而非字符长度；若 tokenizer 降级，trace 明确标记估算模式。
- [x] 实现相邻 chunk 合并、跨文档多样性、同文档最大占比、相似重复抑制、注入过滤与安全最小证据窗口。
- [x] 证据不足时输出空或不足 Evidence Pack 与对应状态，不强行截取低相关资料。
- [x] 单元测试覆盖：相邻/不相邻 line window、同文档过度占用、token 预算、重复 chunk、注入 chunk、缺 parent_text、rerank 失败。

**完成条件：**

- Evidence Pack 只含可定位安全证据；
- 预算、去重和多样性规则均有行为测试；
- rerank 可独立替换和 mock。

---

## T04 Citation Manifest、结构化回答契约与验证器

**状态：** `[x]`
**依赖：** T03

**文件范围：**

- `backend/app/services/rag_core/citation_manifest.py`
- `backend/app/services/rag_core/answer_composer.py`
- `backend/app/services/rag_core/citation_validator.py`
- `backend/app/services/rag_citation_prompt.py`
- `backend/app/services/rag_prompt_builder.py`（仅导出 citation Prompt 接口）
- `backend/app/services/rag_core/contracts.py`
- `backend/tests/test_citation_manifest.py`
- `backend/tests/test_citation_validator.py`
- `backend/tests/test_rag_answer_composer.py`
- `backend/tests/test_rag_prompt_builder_citations.py`

**工作项：**

- [x] 为每项 Evidence Reference 生成稳定、可复现的 citation ID，包含条目、chunk 与 corpus version 派生信息但不泄露正文。
- [x] 将 Evidence Pack 用稳定顺序和明确 XML/结构化边界传入 Prompt；所有证据继续被声明为不可信资料。
- [x] Prompt 输出 answer status、答案、关键主张和 citation 列表、不确定性；不得要求模型额外生成 CoT。Provider 原生返回 reasoning 时，按既有 QA 契约原样透传给所属用户，但不得作为 citation 依据。
- [x] 实现 parse failure 的安全降级：格式不合法时不应崩溃，也不能把未验证引用标记为 supported。
- [x] CitationValidator 验证 citation 属于本次 Evidence Pack、行号/条目可定位、supported 关键 claim 至少有一条有效引用。
- [x] 保留旧 Provider 的纯文本响应兼容路径；在 strict citation flag 关闭时返回 warning，在开启时降级状态。
- [x] 所有 LLM Provider、embedding、rerank 测试必须 mock；不得发真实 HTTP。

**完成条件：**

- 伪造 citation、跨请求 citation、缺 citation claim、格式错误响应均有负例测试；
- Provider 原生 reasoning 可按既有 `qa_records.reasoning` 用户归属范围持久化并显示，但不会复制进 trace、评测、指标或日志，也不会参与 citation 判断；
- legacy prompt cache 稳定前缀不被动态 trace 破坏。

---

## T05 QA 兼容、Trace 持久化、授权 API 与数据最小化

**状态：** `[x]`
**依赖：** T01、T04

**文件范围：**

- `backend/app/routes/qa.py`
- `backend/app/services/rag_core/trace_recorder.py`
- `backend/app/models/qa.py`
- `backend/app/models/__init__.py`
- `backend/app/routes/admin_rag.py`（新薄路由；不得扩展巨型 `admin.py`）
- `backend/app/services/rag_core/public_rag_executor.py`
- `backend/app/services/rag_core/public_rag_result_factory.py`
- `backend/app/services/rag_core/engine_adapter.py`
- `backend/app/services/rag_core/qa_trace_persistence.py`
- `backend/app/services/rag_core/qa_record_payload.py`
- `backend/tests/test_qa_rag_core_api.py`
- `backend/tests/test_rag_trace_authorization.py`

**工作项：**

- [x] 把 v2 结果适配到既有 ask / SSE 事件，同时新增 `answer_status`、`citations`、`trace_id`、`pipeline_version`。
- [x] 将 citation manifest、answer status 和 trace ID 以加性字段存入 QA record；旧记录保持读取兼容。
- [x] TraceRecorder 只保存 stage 计数、rank、分数、ID、哈希、耗时、warning 和版本；禁止保存正文、query、Prompt、CoT。
- [x] 新建管理员 RAG 路由模块，提供分页 evaluation run 和受控 trace 查看；完成角色鉴权和对象归属鉴权。
- [x] 本人可读自己的 evidence 摘要；普通用户不可读取其他人的记录、trace 或管理评测数据。
- [x] trace 写入失败不得阻断主回答，但必须安全 logger 记录 error type/stage/request ID。

**完成条件：**

- [x] 真实公共 RAG v2 执行器接线 Candidate → Rerank → Evidence → Citation → Answer；无可定位证据或检索故障时禁止调用 Provider 臆测回答。
- 非流式、流式、会话历史、旧 record、Provider 失败、trace 写入失败均有测试；
- 负向授权测试覆盖未登录、他人 record、非管理员诊断接口；
- 新增 trace/evaluation 数据库存储无完整正文、query、Prompt 或 reasoning；既有 `qa_records.reasoning` 仅按当前用户归属访问。

---

## T06 评测集、离线评测运行与策略比较报告

**状态：** `[-]`
**依赖：** T02、T03、T04、T05

**文件范围：**

- `backend/rag_eval_cases.jsonl`
- `database/seed_rag_eval_cases.sql`
- `backend/app/scripts/rag_evaluate.py`
- `backend/app/services/rag_core/evaluator.py`
- `backend/app/services/rag_core/evaluation_metrics.py`
- `backend/tests/test_rag_evaluator.py`
- `backend/tests/test_rag_evaluation_metrics.py`

**工作项：**

- [ ] 将受版本控制的 `backend/rag_eval_cases.jsonl` 作为人工可审阅标签源，扩展活跃评测 case 至少 200 条；每条添加稳定 case_key、category、difficulty、expected evidence、expected answer status 与审核说明，且不保存文档正文。
- [ ] 评测运行明确选择 legacy 或 v2 pipeline version，并保存 corpus/prompt/embedding/reranker/config fingerprint。
- [ ] 实现检索指标：Recall@20、Recall@40、MRR@20、nDCG@10；必须同时输出总分和按类别分数。
- [ ] 实现 Evidence Pack 指标：预期 evidence 覆盖、噪声比例、来源多样性、token 占用。
- [ ] 实现可确定性校验：citation 是否存在、是否属于本次 pack、expected status 是否符合；LLM judge 只可作为非门禁辅助，默认关闭。
- [ ] 生成对比报告：legacy vs v2、失败 case、失败阶段、性能分布和回归结论。
- [ ] 报告文件保存到既有 gitignore 路径，数据库仅保存摘要和版本；禁止报告中落盘正文。

**完成条件：**

- 同一冻结数据与版本可以重复获得相同检索指标；
- 评测单元测试无需外部服务；
- 报告能为 T09 发布决定提供完整证据。

---

## T07 前端证据交互与研发诊断体验

**状态：** `[-]`
**依赖：** T05、T06
**设计确认：** 2026-08-14，采用“QA 风格可核验证据卡 + 受控原文跳转”；不展示 dense cosine 百分比或未校准回答置信度。

**文件范围：**

- `backend/app/routes/qa.py`（仅保留鉴权与响应薄层）
- `backend/app/routes/admin_rag.py`（仅保留管理员鉴权与脱敏响应薄层）
- `backend/app/services/rag_core/citation_evidence.py`
- `backend/app/services/rag_core/admin_trace_summary.py`
- `backend/app/services/rag_core/qa_record_payload.py`
- `backend/tests/test_qa_evidence_api.py`
- `backend/tests/test_rag_trace_authorization.py`
- `frontend/src/api/index.js`
- `frontend/src/composables/chat/useCitationEvidence.js`
- `frontend/src/composables/admin/useRagDiagnostics.js`
- `frontend/src/features/chat/citationPresentation.js`
- `frontend/src/features/chat/citationManifest.js`
- `frontend/src/features/admin/ragDiagnosticsPresentation.js`
- `frontend/src/features/admin/ragTracePresentation.js`
- `frontend/src/features/admin/ragEvaluationPresentation.js`
- `frontend/src/components/chat/AnswerEvidenceSummary.vue`
- `frontend/src/components/chat/AnswerCitationList.vue`
- `frontend/src/components/chat/LegacySourceList.vue`
- `frontend/src/components/chat/CitationDetailDrawer.vue`
- `frontend/src/components/chat/AnswerUncertaintyPanel.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/components/chat/ChatUserMessage.vue`
- `frontend/src/components/chat/ChatMessageActions.vue`
- `frontend/src/components/chat/ChatSources.vue`（删除旧的前端直连知识详情逻辑）
- `frontend/src/composables/chat/useChat.js`
- `frontend/src/composables/chat/useConversationMessages.js`
- `frontend/src/features/chat/i18n.js`
- `frontend/src/views/QA.vue`
- `frontend/src/views/admin/RagDiagnostics.vue`
- `frontend/src/components/admin/ragDiagnostics/`
- `frontend/src/router/index.js`
- `frontend/src/views/AdminLayout.vue`
- `frontend/tests/agent-chat-evidence-presentation.test.mjs`
- `frontend/tests/agent-rag-diagnostics-presentation.test.mjs`

**工作项：**

- [x] 扩展 owner-scoped `GET /api/qa/records/<record_id>/evidence`：保留 manifest 兼容字段，新增按 record + `citation_id` 验证后的 citation detail、限长纯文本预览、主张覆盖数和公共知识库导航目标；不新增迁移，不允许从 legacy source 猜测文档 ID。
- [x] 仅对 manifest 中可解析、已发布的公共 `KnowledgeItem` 返回 `document.knowledge_id`；跨用户 record、伪造 citation、非法 document_id、已删除/未发布文档、非法 manifest 与无 citation 的旧记录均覆盖安全返回，不泄露正文或对象存在性。
- [x] 移除“dense cosine × 100 = 相似度百分比”的产品表达；`confidence` 仅以“检索辅助信号（非正确率）”高/中/低/暂不可用显示，不能展示为回答置信度百分比。
- [x] 新建 QA 风格 `AnswerEvidenceSummary`、`AnswerCitationList`、`LegacySourceList`、`CitationDetailDrawer`、`AnswerUncertaintyPanel`：使用现有 `--chat-*` tokens、暗色主题和聊天内容宽度；v2 引用标题/按钮可进入知识库原文，预览、状态、行号、主张覆盖和辅助信号清晰可见；legacy source 仅以只读摘要保留。
- [x] `CitationDetailDrawer` 与各展示组件只通过 props/emit 协作；新增 `useCitationEvidence` 统一处理 API 调用、缓存、错误、焦点恢复和后端授权后的路由导航；移除 `ChatSources.vue` 中组件内 API 调用。
- [x] 流式回答中先稳定渲染正文和状态，再处理 citation manifest；SSE 断流、无 done、manifest 缺失/非法、legacy record、evidence 请求失败时显式显示降级或兼容提示，不能静默隐藏；历史 record 已保存的 `sources` 显示为只读来源卡，不伪造 citation、不显示相似度或正文、不支持原文跳转。
- [x] 新增管理员诊断页 `/admin/rag-diagnostics`：仅显示后端白名单后的脱敏数量、排名、耗时、策略版本、warning 与评测摘要；具备 loading/empty/error/success 状态，前端 role guard 与后端 403 双重覆盖，API 不下发候选明细、document ID、request ID 或 query fingerprint。
- [x] 使用 `BaseIcon`；管理员页面使用 `BasePanel`、`BaseBadge`、`BaseButton`。聊天页面不引入与 QA token 冲突的 Security Workbench 蓝色视觉；所有新增样式为 scoped SCSS，覆盖桌面/平板/手机。
- [x] 编写真实边界测试：citation 越权/伪造/文档失效/预览截断/旧记录，状态与辅助信号归一化，SSE 断流与无效 manifest，管理员路由与 trace API 拒绝普通用户；外部 API 全部 mock。
- [x] 运行 `npm --prefix frontend run test:agent` 与 `npm --prefix frontend run build`；不运行带 `--fix` 的 lint 命令；后端先跑 focused tests 再跑完整 pytest。

**完成条件：**

- 正常、证据不足、冲突、降级、旧 QA record、citation detail 请求失败、SSE 失败均有组件或纯函数覆盖；
- 每一条 v2 citation 可在授权后看到预览、状态、行号并进入对应公共知识库原文；前端不再直连或猜测知识文档 ID；
- 手机端引用列表、抽屉、原文跳转和键盘操作可用，视觉与当前 QA 聊天页的亮/暗主题匹配；
- 普通用户不能进入管理员诊断页、读取 trace 或评测详情；
- 前端构建、针对性前端测试、focused 后端测试、全量后端测试与 `git diff --check` 均通过。

**自动化验证证据（2026-08-14）：**

- `backend\venv\Scripts\python.exe -m pytest tests\test_qa_evidence_api.py tests\test_qa_rag_warnings.py tests\test_rag_trace_authorization.py -q`：42 passed；覆盖 owner scope、伪造 citation、未发布文档、预览截断、legacy record、SSE 降级与管理员 API 拒绝普通用户。
- `npm --prefix frontend run test:agent`：46 passed；覆盖 citation manifest 缺失/重复/伪造、流式/legacy 状态、未校准检索辅助信号、诊断 trace 白名单、评测摘要白名单与 failure stage 聚合。
- `npm --prefix frontend run build`：通过；使用当前项目既有 Sass/CSS nesting 和大 chunk 警告，但无新增构建失败。
- `backend\venv\Scripts\python.exe -m pytest tests -q`：1271 passed，1 skipped；`backend\venv\Scripts\python.exe -m compileall -q app tests`：通过。
- 仅剩用户管理服务上的浏览器人工验收（H-09/L-04）：需验证亮/暗主题下的桌面、平板、手机断点，以及真实已发布知识文档的跳转；本轮未启动、停止或重启任何常驻服务。

---

## T08 Observability, Feature Flags, and Rollback

**Status:** `[-]`
**Dependencies:** T05, T06, T07

**Files:**

- `backend/app/services/rag_core/metrics.py`
- `backend/app/services/rag_core/metrics_policy.py`
- `backend/app/services/rag_core/execution_observer.py`
- `backend/app/services/rag_core/public_rag_executor.py`
- `backend/app/services/rag_core/trace_recorder.py`
- `backend/app/services/rag_core/qa_trace_persistence.py`
- `backend/app/services/observability.py`
- `backend/app/routes/admin_rag.py`
- `backend/app/config.py`
- `backend/tests/test_rag_metrics.py`
- `backend/tests/test_public_rag_executor.py`
- `backend/tests/test_rag_trace_recorder.py`
- `backend/tests/test_rag_trace_authorization.py`
- `rag-redesign/spec.md`
- `rag-redesign/tasks.md`
- `rag-redesign/checklist.md`

**Completed work:**

- [x] Record V2 candidate/rerank/evidence/generation/retrieval-total timings, answer-status distribution, degradation count, citation-validation failures, and pipeline version through a bounded in-process registry.
- [x] Enforce controlled metric names and low-cardinality labels. Query, title, user ID, document ID, citation ID, raw errors, prompts, and document text are rejected as labels and never appear in the snapshot.
- [x] Resolve V2, strict-citation, diagnostics, and metrics-sample flags from validated startup configuration. Runtime diagnostics return the effective non-sensitive snapshot; no mutable admin flag API is exposed.
- [x] Document a configuration-only rollback: set `RAG_PIPELINE_V2_ENABLED=false`, restart the user-managed backend, and verify legacy mode. No database migration, reset, or rollback is involved.
- [x] Add failure-injection coverage for Qdrant, reranker, LLM, citation validator, and trace DB failures, including safe response behavior and metric classification.

**Completion conditions:**

- V2 execution and trace-persistence failure branches emit only controlled metrics;
- Configuration rollback behavior is covered by code tests; a user-managed runtime rehearsal remains a release gate in `checklist.md`;
- Documentation contains no secrets, tokenized URLs, production endpoints, queries, or document content.

**Automated implementation record (2026-08-14):**

- `RagRuntimeMetrics` is worker-local (`scope=process`), thread-safe, samples at most `RAG_METRICS_SAMPLE_LIMIT` values per allowed stage, and caps metric series at 24. It deliberately does not claim multi-worker aggregation.
- `GET /api/admin/rag/runtime-metrics` is JWT-admin-only and returns 404 when `RAG_DIAGNOSTICS_ENABLED=false`. The payload contains only an effective non-sensitive flag snapshot and controlled aggregate counters/latency percentiles.
- The current per-stage execution instrumentation applies to the V2 executor. Legacy remains the rollback target and quality baseline; legacy-vs-V2 latency comparison must be established by the T09 runtime evaluation, not inferred from this in-process registry.
- Focused verification: `backend\venv\Scripts\python.exe -m pytest tests\test_rag_metrics.py tests\test_public_rag_executor.py tests\test_rag_trace_recorder.py tests\test_rag_trace_authorization.py tests\test_rag_core_contracts.py -q` completed with 40 passed. `backend\venv\Scripts\python.exe -m compileall -q app tests` completed successfully.
- Full verification: `backend\venv\Scripts\python.exe -m pytest tests -q` completed with 1286 passed and 1 skipped. The existing suite emitted dependency and SQLAlchemy warnings; process exit status was 0.
- J-04/J-05 and L-05 remain open because quality comparison, p95 release gating, and a real configuration rollback rehearsal require the user-managed runtime environment.

---

## T09 全链路验收、灰度与项目叙事

**状态：** `[ ]`
**依赖：** T06、T07、T08

**文件范围：**

- `rag-redesign/checklist.md`
- `README.md`（仅在用户批准更新时）
- `backend/tests/`
- `frontend/` 对应测试

**工作项：**

- [ ] 跑完整后端 pytest、compileall、前端 build 与 `git diff --check`。
- [ ] 在用户管理的本地服务上，使用脱敏问题完成 legacy/v2 对照和 SSE 浏览器验收；不读取无关历史记录。
- [ ] 运行 200+ case 评测，检查所有发布门禁，并登记报告路径和版本。
- [ ] 抽检 30 条 supported 答案，由人工登记 citation correctness；发现 P0 伪造引用、越权或敏感泄露必须停止发布。
- [ ] 按 Feature Flag 对少量测试账户灰度启用；记录回滚操作和结果。
- [ ] 形成一页可演示项目说明：问题、架构图、指标对比、失败案例、治理边界、回滚策略；不得夸大指标或虚构上线效果。
- [ ] 最终逐项完成 `checklist.md`，再向用户请求代码提交与推送授权。

**完成条件：**

- 所有 blocker 均通过；
- 有可复现实验数据和测试证据；
- 用户确认是否提交和推送；未授权时不得 commit/push。

---

## 任务完成判定

只有 T00–T09 全部标记 `[x]`、所有 blocker 在 `checklist.md` 通过、用户接受最终评测结果且没有未解决 P0/P1 风险时，本改造才可标记为完成。

### T06 完成记录（2026-08-14）

- 受版本控制的 `backend/rag_eval_cases.jsonl` 已扩展到 200 条 active case，覆盖 concept、identifier、defense、multihop、alias、insufficient、conflict、injection 八类场景；标签源不包含知识库正文。
- `database/seed_rag_eval_cases.sql` 仅写入受控 case 标签、预期 evidence/status/difficulty；SQL 使用加性、幂等的种子写法，不输出 query 或文档正文。
- `evaluation_contracts`、`evaluation_metrics`、`evaluator`、`evaluation_runtime`、`evaluation_persistence` 与 CLI 已支持按 `--pipeline`、`--corpus-version` 生成脱敏的 legacy/v2 可比报告。
- 自动化回归使用 fake Pipeline、Provider、Embedding 与 Rerank；T06 完成时的后端全量 pytest 为 1254 passed、1 skipped，没有自动化真实 HTTP 请求。
- 真实 200+ case 的 legacy/v2 对照与发布门禁仍属于 T09 的用户管理环境验收，不能以自动化结构测试替代实际质量结论。


### T09 implementation progress: offline release gate verifier

**Status:** `[x]`

- [x] Add `rag_core/release_gate.py` as a pure verifier for two sanitized evaluation
  reports; it must not access Flask, providers, database records, or source texts.
- [x] Add `app/scripts/rag_release_gate.py` with strict backend-root filename
  validation, sanitized JSON output, and shell-friendly decision exit codes.
- [x] Add regression tests for comparability, metric boundaries, negative/injection
  safety, unsafe report content redaction, input immutability, and CLI path rules.
- [ ] Run the verifier against user-generated 200+ case legacy/V2 reports and record
  the result in the final evidence table. Automated comparison cannot replace the
  manual citation audit or rollback rehearsal.
