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

**状态：** `[ ]`
**依赖：** T05、T06

**文件范围：**

- `frontend/src/components/chat/AnswerEvidenceSummary.vue`
- `frontend/src/components/chat/AnswerCitationList.vue`
- `frontend/src/components/chat/CitationDetailDrawer.vue`
- `frontend/src/components/chat/AnswerUncertaintyPanel.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/composables/chat/useChat.js`
- `frontend/src/composables/chat/useConversationMessages.js`
- `frontend/src/api/index.js`
- `frontend/src/views/security/RagDiagnostics.vue`
- `frontend/src/components/security/ragDiagnostics/`
- 前端对应测试文件

**工作项：**

- [ ] 移除“dense cosine × 100 = 相似度百分比”的产品表达；替换为证据状态、引用数量和行号。
- [ ] 为 `[C#]` 引用提供可访问的点击、键盘焦点和详情抽屉；详情 API 不允许前端直接猜测文档 ID。
- [ ] 展示 supported/insufficient/conflicting/degraded 四种状态及可执行的用户提示。
- [ ] 流式回答中先稳定渲染状态/正文，再接收 citation manifest；断流或无效 manifest 显示降级，而非静默隐藏来源。
- [ ] 新建管理员诊断页：仅显示脱敏数量、排名、耗时、策略版本和 warning；必须有 loading/empty/error/success 骨架状态。
- [ ] 使用 `BaseIcon`、`BaseBadge`、`BasePanel`、`BaseButton`，遵循三断点和 scoped SCSS；不得把 API 逻辑塞进展示组件。
- [ ] 运行 `npm --prefix frontend run build`；不运行带 `--fix` 的 lint 命令。

**完成条件：**

- 正常、证据不足、冲突、降级、旧 QA record、SSE 失败均有组件/交互覆盖；
- 手机端引用列表可用；
- 用户不可进入管理员诊断页或读取 trace。

---

## T08 观测、告警、Feature Flag 与回滚

**状态：** `[ ]`
**依赖：** T05、T06、T07

**文件范围：**

- `backend/app/services/rag_core/metrics.py`
- `backend/app/services/observability.py`
- `backend/app/config.py`
- `backend/tests/test_rag_metrics.py`
- `README.md` 或项目既有运维文档（仅记录非敏感配置与回滚步骤）

**工作项：**

- [ ] 记录 retrieval/rerank/evidence/generation 阶段耗时、降级率、citation validation failure、answer status 分布与 pipeline version。
- [ ] 定义受控指标命名和低基数标签；不得把 query、document title、用户 ID 或 citation ID 作为 metrics label。
- [ ] 实现 v2 flag、strict citations flag、diagnostics flag 的配置优先级与回退行为。
- [ ] 写出一键配置回滚流程：关闭 v2 即回到 legacy；不得依赖数据库回滚。
- [ ] 对 Qdrant/reranker/LLM 失败、trace DB 失败、citation validator 失败执行故障注入测试。

**完成条件：**

- 每个 status 和降级分支有可观测指标；
- 回滚在本地配置切换中可验证；
- 文档不含秘密、URL token 或生产信息。

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

### T06 ???????2026-08-14?

- ?????? `backend/rag_eval_cases.jsonl`?200 ? active case?8 ????concept/identifier/defense/multihop/alias/insufficient/conflict/injection?????????
- `database/seed_rag_eval_cases.sql`?? query ?? insert?????? seed ? evidence/status/difficulty ??????? SQL??????????
- ?? `evaluation_contracts`?`evaluation_metrics`?`evaluator`?`evaluation_runtime`?`evaluation_persistence`?CLI ???? `--pipeline` ? `--corpus-version`?
- ????`backend\venv\Scripts\python.exe -m pytest tests -q` -> 1254 passed, 1 skipped??? Provider/Embedding/Rerank ?????????
- ?????????? 200 ????????????????? legacy/v2 ???????????? T06 ??????
