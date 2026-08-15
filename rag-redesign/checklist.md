# CyberGuard Enterprise RAG Core 验收清单

> 使用方式：每项填写 `PASS / FAIL / N/A`、验证日期、证据命令或报告路径。
> Blocker 项任一失败，禁止默认启用 RAG v2。
> 本清单与 `rag-redesign/spec.md`、`rag-redesign/tasks.md` 一起构成实施唯一依据。

---

## A. 编码前基线与工作区保护

- [x] **A-01 BLOCKER** 已阅读并确认 `spec.md`、`tasks.md`、本清单；当前实施范围仅为公共 RAG Core。
- [x] **A-02 BLOCKER** `git status --short` 已记录；不存在会被本任务覆盖的用户改动。
- [x] **A-03 BLOCKER** 已确认使用 `backend/venv/Scripts/python.exe`；未使用系统 Python。
- [x] **A-04** 已记录数据库公共知识 aggregate、Qdrant collection point count/配置；未导出正文、用户问题或秘密。
- [x] **A-05 BLOCKER** 已运行并保存 legacy baseline；报告包含 pipeline/corpus/embedding/reranker 配置指纹。
- [x] **A-06 BLOCKER** CI 后端步骤可解析，compile 与 pytest 都有有效、独立的 GitHub Actions step。
- [x] **A-07** 已审计现有 18 个评测 case 的规模与字段能力，并登记“仅检索命中、无 evidence/status 标注”的局限；正式 case 标注移至 T06。

## B. 架构与模块边界

- [x] **B-01 BLOCKER** 新实现集中在 `backend/app/services/rag_core/`；没有继续向 `enhanced_rag_engine.py` 叠加复杂职责。
- [x] **B-02 BLOCKER** Route 只负责编排、鉴权、序列化；不包含 Qdrant、RRF、rerank 或 citation 业务逻辑。
- [x] **B-03** `EnterpriseRagPipeline.execute/stream` 是调用方唯一主接口；内部阶段可单测、可替换。
- [x] **B-04** legacy `EnhancedRAGEngine` 在 v2 flag 关闭时无行为回归。
- [x] **B-05** 配置指纹稳定，不含用户信息、随机值或 secrets。

## C. 数据库、迁移与兼容

- [x] **C-01 BLOCKER** 新迁移为 `038_enterprise_rag_core.sql`，仅包含加性 DDL。
- [x] **C-02 BLOCKER** `database/init.sql` 与迁移同步。
- [x] **C-03 BLOCKER** migration runner 注册 038，重复执行安全。
- [x] **C-04** `qa_records` 的 `answer_status`、citation manifest、trace ID、pipeline version 对旧记录均可为空。
- [x] **C-05** trace/evaluation 表没有保存文档正文、完整 query、Prompt、CoT、Authorization 或 Token。
- [x] **C-06** 迁移测试覆盖空库、已有 QA 记录和重复应用。
- [x] **C-07** 未对任何数据库执行 reset、drop、truncate 或破坏性操作。

**T01 证据（2026-08-14）：**

- `backend/tests/test_rag_core_contracts.py`：契约 fake、配置非法值、稳定指纹、legacy ask/stream flag 回退，以及原始 CoT 不进入 trace/manifest。
- `backend/tests/test_rag_core_migration_contract.py`：038 仅加性 SQL、`init.sql` 同步、旧 QA 空字段兼容、fake 空 migration registry 首次/重复执行。
- 未对任何真实数据库执行迁移；C-06 的执行语义为隔离 fake migration runner，真实开发库应用仍需显式确认。
- 全量后端回归：`backend\\venv\\Scripts\\python.exe -m pytest tests -q`，结果 `1180 passed, 1 skipped`；跳过项为环境不支持创建符号链接。

---
## D. Candidate Retrieval 与 Qdrant

- [x] **D-01 BLOCKER** `knowledge_embeddings` 原有 dense + BM25 行为保持兼容。
- [x] **D-02 BLOCKER** hybrid 检索单次请求只执行一次 dense 查询和一次 BM25 查询；重复 lexical query 有回归测试。
- [x] **D-03** Candidate 可区分 dense-only、BM25-only、both、lexical-only degraded。
- [x] **D-04** dense/BM25/RRF/rerank 特征分别命名，未混进单一“similarity”语义。
- [ ] **D-05** 空 query、embedding 降级、Qdrant 故障、非法 metadata 均安全处理。
- [x] **D-06** candidate trace 不含 text/parent_text/query 原文。
- [x] **D-07** CVE/CWE、端口、配置键、中英文别名均有检索测试。

**T02 证据（2026-08-14）：**

- `test_qdrant_hybrid_trace.py` 验证 dense/BM25 各一次、融合来源路径与 lexical-only 降级。
- `test_rag_candidate_retriever.py` 验证 CVE/CWE、端口、配置键、中英混合、空问题、embedding 降级与 Qdrant 异常；trace 不含正文。

---

## E. Rerank 与 Evidence Pack

- [x] **E-01 BLOCKER** reranker 不可用时明确 skipped/failed，不伪装为成功 rerank。
- [x] **E-02** rerank 输入、输出、耗时和失败类型进入脱敏 trace。
- [x] **E-03 BLOCKER** Evidence Pack 使用 tokenizer token budget；字符数不得作为唯一截断依据。
- [x] **E-04** 相邻 chunk 合并保持真实行号；不相邻 chunk 不伪造连续窗口。
- [x] **E-05** 同文档占比、多样性、重复抑制和注入剔除均有测试。
- [x] **E-06 BLOCKER** 证据不足时不强行填充低相关 chunk。
- [ ] **E-07** Evidence Pack 不跨公共/私有 collection，且本期只使用 `knowledge_embeddings`。

**T03 证据（2026-08-14）：**

- `venv\Scripts\python.exe -m pytest tests\test_rag_rerank_stage.py tests\test_evidence_pack_builder.py tests\test_text_chunker.py -q`：22 passed；覆盖 Provider 无分数/异常/NaN、预算等值和越界、来源垄断、相邻与非相邻行号、注入、重复、缺父窗口、不可定位证据和计数器故障。
- `venv\Scripts\python.exe -m compileall -q app tests`：通过。
- `venv\Scripts\python.exe -m pytest tests -q`：1197 passed，1 skipped；测试仅使用 fake reranker/token counter，不发起真实 Provider HTTP。
- E-07 留待 T05 的公共 QA 管道接线验证；本阶段只处理已传入的 `Candidate`，不接触任何 collection。

## F. Prompt、回答状态与 Citation

- [x] **F-01 BLOCKER** 系统 Prompt 前缀稳定；Evidence Pack 被明确标记为不可信资料。
- [x] **F-02 BLOCKER** 仅允许当前 QA 记录所属用户查看 Provider 原生 CoT；CoT 与证据依据明确区分，不参与 citation、confidence、trace、评测或日志，且不得跨用户读取。
- [x] **F-03** 支持 `supported`、`insufficient_evidence`、`conflicting_evidence`、`degraded` 四种状态。
- [x] **F-04 BLOCKER** 每个 supported 关键 claim 至少有一个本次 Evidence Pack 中的有效 citation。
- [x] **F-05 BLOCKER** 伪造 citation、跨请求 citation、无 citation claim、格式错误输出均被验证器拦截或降级。
- [x] **F-06** citation ID 可复现，映射到 knowledge item、chunk、corpus version、title path 和行号。
- [x] **F-07** strict citation flag 关闭时保持兼容且带 warning；开启时不合格结果安全降级。

**T04 证据（2026-08-14）：**

- `venv\Scripts\python.exe -m pytest tests\test_citation_manifest.py tests\test_citation_validator.py tests\test_rag_answer_composer.py tests\test_rag_prompt_builder_citations.py -q`：12 passed；覆盖稳定 ID、正文脱敏、证据 XML 转义、伪造/跨请求 ID、缺 citation 的 supported、重复 manifest、格式失败与 strict/兼容降级。
- `venv\Scripts\python.exe -m compileall -q app tests`：通过；其后 `venv\Scripts\python.exe -m pytest tests -q`：1207 passed，1 skipped。最后补充的四状态测试仅改测试文件，并已聚焦通过。
- 自动化测试未构造真实 LLM/embedding/rerank Provider 请求；全部使用静态 JSON、manifest 和 fake 计数器。
- F-02 已由 T05 完成：`test_reasoning_is_visible_to_owner_and_hidden_from_other_user` 验证 Provider 原生 CoT 仅由当前记录所属用户读取，evidence/trace/admin 返回均不包含 reasoning。

## G. API、授权与持久化

- [x] **G-01 BLOCKER** `/api/qa/ask` 与 `/api/qa/ask/stream` 对旧客户端兼容。
- [x] **G-02** 新响应字段包括 answer status、citations、trace ID、pipeline version 和 retrieval summary。
- [x] **G-03 BLOCKER** 用户只能读取自己的 QA record/evidence；他人记录返回拒绝或 404。
- [x] **G-04 BLOCKER** 诊断 trace 和 evaluation run 接口只能由授权管理员访问。
- [x] **G-05** trace 写入失败不会中断回答，但会记录安全的 error type/stage/request ID。
- [x] **G-06** SSE 在 citation manifest 缺失或断流时显示 degraded，不伪造来源。
- [x] **G-07** API error 不泄露 stack trace、数据库错误、Prompt 或文档正文。
**T05 证据（2026-08-14）：**

- `backend/tests/test_public_rag_executor.py`：公共 Candidate → Rerank → Evidence → Citation → Answer 全链路；覆盖批量 embedding 向量扁平化、Qdrant 故障、无可定位证据、无效/伪造 citation、关闭 rerank 和 trace 不含 query/正文/CoT。
- `backend/tests/test_qa_rag_warnings.py`：非流式与 SSE 的 v2 元数据、旧字段兼容、缺 citation/断流降级、异常脱敏、QA record/会话读取、本人 evidence endpoint、跨用户 CoT 隔离和 trace 写入失败。
- `backend/tests/test_rag_trace_recorder.py` 与 `backend/tests/test_rag_trace_authorization.py`：trace 二次脱敏、数据库写入失败回滚与安全日志、未登录/非管理员拒绝、管理员 trace/evaluation 分页返回不暴露 report path。
- `backend\venv\Scripts\python.exe -m compileall -q app tests`：通过；`backend\venv\Scripts\python.exe -m pytest tests -q`：1236 passed，1 skipped。所有新增外部边界均为 fake/provider mock，无真实 LLM、embedding 或 rerank HTTP。
- 未启动、停止、重启 Flask/Qdrant/Redis，也未对真实数据库应用迁移；v2 仍默认由 `RAG_PIPELINE_V2_ENABLED=false` 关闭，尚未进行人工灰度对照。

## H. 前端交互与无障碍

- [x] **H-01 BLOCKER** 不再把向量 cosine 显示成“xx% 相似度”或“回答置信度”。
- [x] **H-02** Answer status 和证据不足/冲突/降级状态清晰、可操作且有用户可理解文案。
- [x] **H-03** Citation list 以稳定 `[C#]` 标识展示标题、标题路径、行号、主张覆盖和受限预览。
- [x] **H-04 BLOCKER** Citation detail 仅通过 owner-scoped evidence API 加载；前端不能由 legacy `sources`、`doc_id`、标题或 URL 猜测/拼接知识文档 ID。
- [x] **H-05** 后端只为已发布公共知识的有效 citation 返回导航目标；跨用户 record、伪造 citation、非法/失效 document 与 malformed manifest 不泄露正文或对象存在性。
- [x] **H-06** 未校准 `confidence` 仅显示为“检索辅助信号（非正确率）”高/中/低/暂不可用；answer status、citation validity 与覆盖数始终优先。
- [x] **H-07** 所有新 Vue 页面遵守编排层与组件层分离；展示组件不直接调用 API，`useCitationEvidence` 统一承担请求、缓存和已授权导航。
- [x] **H-08** 聊天证据组件使用现有 QA `--chat-*` token、内容宽度与亮/暗主题，不混入 Security Workbench 蓝色卡片风格；管理员诊断页使用 BaseIcon/BaseButton/BaseBadge/BasePanel。
- [ ] **H-09** 桌面、平板、手机三断点均验证；引用详情可键盘操作、焦点正确恢复，手机端标题、状态、行号与原文跳转可用。
- [x] **H-10** loading、empty、error、success、SSE 中断、manifest 非法和旧记录状态都有 UI/纯函数覆盖，不允许静默隐藏证据失败；历史 record 的旧 `sources` 以只读卡片保留标题、来源和行号，不允许伪造 citation、正文或原文跳转。
- [x] **H-11 BLOCKER** 普通用户无法进入 `/admin/rag-diagnostics`，且后台 trace/evaluation API 对非管理员返回 403；前端路由守卫不是唯一防线。


**T07 自动化证据（2026-08-14）：**

- Citation API focused tests：42 passed；公共知识导航仅由 record + manifest + published KnowledgeItem 共同授权。
- 前端 `test:agent`：46 passed；含 citation 状态/辅助信号、非法 manifest、诊断数据白名单与泄露防护测试。
- 前端 build：通过；完整后端 pytest：1271 passed，1 skipped；compileall：通过。
- **H-09 保持待人工验收**：响应式断点、亮/暗主题、键盘焦点恢复和真实知识原文跳转需要在用户管理的运行中服务上完成。
## I. 评测集与质量指标
- [ ] **I-01 BLOCKER** 活跃评测 case 不少于 200，且各类别数量、难度、来源可审计；受版本控制 JSONL 为人工审阅标签源且不含文档正文。
- [ ] **I-02 BLOCKER** 每个 case 包含 expected evidence 和 expected answer status；不可验证 case 已停用或移除。
- [x] **I-03** 评测可分别运行 legacy/v2，输出固定 pipeline/corpus/config 指纹。
- [x] **I-04 BLOCKER** 报告至少有 Recall@20、Recall@40、MRR@20、nDCG@10。
- [x] **I-05** 报告有 Evidence Pack 覆盖、来源多样性、token 占用和 citation 确定性指标。
- [ ] **I-06 BLOCKER** `insufficient` 与 `injection` 负例不允许被错误标记为 supported。
- [x] **I-07** 报告按类别展示失败样本、失败阶段与 legacy/v2 对比。
- [x] **I-08** 评测报告不含正文、完整 query、Prompt 或 secrets，且不提交到 Git。

## J. Performance, reliability, and observability

- [x] **J-01** Record V2 candidate/rerank/evidence/generation/retrieval-total latency with bounded p50/p95 samples; scope is explicitly one Flask worker process.
- [x] **J-02** Record controlled degradation/failure counters for embedding, Qdrant, reranker, LLM, citation validator, and trace DB.
- [x] **J-03** Metric labels are low-cardinality and reject query, title, user ID, document ID, citation ID, request ID, raw error, prompt, and document content.
- [x] **J-08** A pure offline release-gate verifier compares sanitized legacy/V2 reports, enforces report comparability and automatic blockers, and emits no query, case-id, title, prompt, or document text. Live evidence remains pending.
- [x] **J-09** The local MySQL RAG migration is idempotent on an older `ADD COLUMN` dialect, and foreign-key column types match `rag_eval_cases.id`; browser QA no longer fails on the missing RAG schema fields.
- [x] **J-10** Local V2 browser smoke verified evidence status, preview, original-document navigation, insufficient-evidence behavior, and prompt-injection non-disclosure; the process was reverted to legacy afterward.
- [ ] **J-04 BLOCKER** v2 release core quality metrics are not below legacy and at least two major quality metrics improve.
- [ ] **J-05 BLOCKER** retrieval p95 is not above 1.25x legacy, or there is user-approved quantitative evidence of the tradeoff.
- [x] **J-06** Code-level Feature Flag test and the effective runtime snapshot confirm that disabling V2 selects legacy without a database rollback. The user-managed runtime rehearsal remains L-05.
- [x] **J-07** Qdrant/reranker/LLM/trace DB/citation-validator fault injection verifies expected safe degradation and controlled metric classification.

## K. 自动化验证

- [x] **K-01 BLOCKER** 所有新增后端单元/集成测试通过，外部 API 均 mock。
- [x] **K-02 BLOCKER** 执行：`backend\venv\Scripts\python.exe -m pytest tests -q`。
- [x] **K-03 BLOCKER** 执行：`backend\venv\Scripts\python.exe -m compileall -q app tests`。
- [x] **K-04 BLOCKER** 执行：`npm --prefix frontend run build`。
- [x] **K-05 BLOCKER** 执行：`git diff --check`。
- [x] **K-06** 如新增前端行为，运行现有针对性前端测试；不运行会自动全量改写的 lint。
- [x] **K-07** 任何真实 Provider/embedding/rerank HTTP 出现在自动化测试中均为拒收。

## L. 人工验收、灰度与回滚

- [ ] **L-01 BLOCKER** 用户管理的本地服务上完成 legacy/v2 同题对照，未启动或重启任何服务。
- [ ] **L-02** 人工抽检至少 30 条 supported 答案；关键主张 citation correctness 至少 90%。
- [ ] **L-03 BLOCKER** 不存在 P0 伪造引用、跨用户访问、敏感数据泄露或把缺证据答案标为 supported。
- [ ] **L-04** 诊断页展示的 trace 与数据库摘要一致，但不泄露正文。
- [ ] **L-05** 已演练 Feature Flag 回滚并登记命令、时间与结果。
- [ ] **L-06** 已输出面试演示材料：架构、前后对比指标、典型失败样本、治理边界与回滚策略。

## M. 最终证据登记表

| 项目 | 结果/数值 | 命令或报告路径 | 日期 | 审核人 |
| --- | --- | --- | --- | --- |
| Legacy baseline | 18 case；Hit@1=0.4444，Hit@3=1.0000，Hit@5=1.0000，MRR=0.7037 | `backend/rag_report_20260814_legacy_baseline.json` | 2026-08-14 | Codex |
| Browser RAG smoke | Normal answer, injection resistance, insufficient-evidence response, history and favorite toggle pass; V2 verifiable citations pending | Local browser acceptance | 2026-08-15 | Codex |
| V2 citation browser smoke | Supported answer: 6 verifiable citations, service-authorized preview, original route; negative and injection cases safely handled; reverted to legacy | Local browser acceptance | 2026-08-15 | Codex |
| Release gate decision | Pending user-generated comparable 200+ case reports | `backend/rag_release_gate_<comparison>.json` | Pending | Pending |
| V2 evaluation run | 未执行 |  |  |  |
| Recall@20 / Recall@40 | 未执行 |  |  |  |
| nDCG@10 / MRR@20 | 未执行 |  |  |  |
| Citation correctness 抽检 | 未执行 |  |  |  |
| Retrieval p95 | 未执行 |  |  |  |
| 后端 pytest | 1286 passed，1 skipped | `backend\\venv\\Scripts\\python.exe -m pytest tests -q` | 2026-08-14 | Codex |
| 前端 build | 通过（既有 Sass/CSS nesting 与 chunk 警告） | `npm --prefix frontend run build` | 2026-08-14 | Codex |
| RAG runtime metrics | Worker-local, bounded, low-cardinality implementation and fault injection tests | `backend\venv\Scripts\python.exe -m pytest tests\test_rag_metrics.py tests\test_public_rag_executor.py tests\test_rag_trace_recorder.py tests\test_rag_trace_authorization.py tests\test_rag_core_contracts.py -q` | 2026-08-14 | Codex |
| Feature Flag 回滚 | 未执行 |  |  |  |
| 最终发布结论 | 未执行 |  |  |  |

## N. 立即拒收条件

出现任一情况，停止默认启用与交付声明：

- [ ] 真实外部 Provider、embedding 或 reranker 被自动化测试调用。
- [ ] 新迁移不是加性的，或未同步 `database/init.sql`。
- [ ] trace/报告/日志泄露 query、文档正文、Prompt、CoT、Token 或凭据。
- [ ] citation 可被模型伪造、跨请求复用、跨用户读取或指向未授权证据。
- [ ] v2 无法通过 Feature Flag 回退 legacy。
- [ ] 仅凭“相似度百分比”或主观聊天体验宣布质量提升。
- [ ] 未跑完整验证便声称已完成。

### T06 完成记录（2026-08-14）

- [x] 受版本控制的评测标签源包含 200 条 active case，类别覆盖 concept、identifier、defense、multihop、alias、insufficient、conflict、injection；标签源未复制知识库正文。
- [ ] 仍需在用户管理的本地环境运行真实 legacy/v2 对照，确认 I-01、I-02、I-06 及发布门禁；该验证不能由数据库种子或 fake Pipeline 测试替代。

### T10 完成记录（2026-08-15）

- [x] 首页 QA 路由在首屏稳定后预加载，真实浏览器中从首页点击“智能问答”后成功进入 `/qa`；预加载器覆盖并发去重、失败后重试和未知路由边界。
- [x] 证据不足回答不再显示“可核验引用”或“已验证引用”：摘要、按钮、资料列表和可访问性标签统一改为“相关参考资料”，并明确不支撑当前结论。
- [x] `conflicting_evidence` 与未知/降级状态分别展示“冲突参考资料”与“待核验资料”，不展示主张覆盖数。
- [x] 已执行：`node --test frontend\tests\chat-citation-presentation.test.mjs frontend\tests\home-route-prefetch.test.mjs`、`npm --prefix frontend run build`、`git diff --check`。
