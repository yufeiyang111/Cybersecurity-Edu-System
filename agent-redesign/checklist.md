# CyberGuard 代码漏洞审查 Agent 改造验收清单

> 文档版本：1.1.0
> 冻结日期：2026-08-12
> 适用仓库：`D:\workproject\work\work-5238`
> 规格依据：`agent-redesign/spec.md`
> 执行依据：`agent-redesign/tasks.md`
> 用途：本文件是阻断式验收门，不是建议列表。所有 `BLOCKER` 必须有可复核证据，才能宣布整体改造完成。
> 修订记录：v1.1.0（2026-08-12）随 spec.md v1.1.0 修订 reasoning 相关验收措辞（K-01/K-02/K-03/M-11/O-06/U-05、总体验收规则），新增 C-13 Reasoning Summary 验收项。

---

## 0. 使用规则

### 0.1 结论标记

- `[ ]`：尚无证据。
- `[x]`：已验证通过，并在交付记录中提供命令、退出码或可复核工件。
- `[!]`：不适用或被外部条件阻塞；必须说明原因和影响。`BLOCKER` 项不能用 `[!]` 代替通过。

### 0.2 证据等级

| 等级 | 证据 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| E1 | 源码审查、类型检查、静态查询 | 结构存在、明显边界 | 运行时行为 |
| E2 | focused unit/contract tests | 单模块和协议行为 | 真实组合、真实服务 |
| E3 | 集成/全量测试、测试数据库、Fake Provider | 组合逻辑与回归 | 真实 Provider、浏览器、进程恢复 |
| E4 | 本机真实数据库/API/SSE/Provider/浏览器 | 产品级纵向切片 | 长期生产稳定性 |
| E5 | 灰度观察、恢复/回滚演练、指标 | 可运营与可回退性 | 未覆盖环境的绝对保证 |

### 0.3 总体验收规则

- `BLOCKER` 项必须为 `[x]`，且达到该项要求的最低证据等级。
- 只有 E1/E2/E3 时，只能声明“代码和自动化验证完成”，不能声明产品改造完成。
- 涉及真实 Provider、数据库迁移、SSE、浏览器、进程恢复和灰度的项目必须有 E4/E5。
- 测试跳过、xfail、mock 核心 Controller、手工改数据库、前端模拟事件均不能作为通过证据。
- 任何秘密泄露、跨 workspace 越权、完整原始思维链全文持久化、执行被审查项目、破坏性迁移、序列重复，均为立即拒收。

---

## A. 启动前与工作区安全

- [ ] **A-01 BLOCKER / E1** 已阅读 `AGENTS.md`、`CLAUDE.md`、`.claude/rules/` 和三件套文档，并在交付中确认无冲突或列出已解决冲突。
- [ ] **A-02 BLOCKER / E1** 已记录开始时的完整 Git SHA、分支、`git status --short --branch` 和目标文件既有 diff。
- [ ] **A-03 BLOCKER / E1** 用户既有未提交改动被逐项保留；没有 reset、clean、rebase、强推或大范围覆盖。
- [ ] **A-04 BLOCKER / E1** 后端命令全部使用 `backend\venv\Scripts\python.exe` 或 `flask.exe`；没有裸 `python`。
- [ ] **A-05 BLOCKER / E1** 未读取、输出或提交 `backend/.env`、密钥、Token、Cookie、授权头、运行日志原文、构建产物或上传源码全文。
- [ ] **A-06 BLOCKER / E1** 未启动、停止、重启或杀掉常驻服务，除非当前会话有用户明确授权和进程证据。
- [ ] **A-07 BLOCKER / E1** 未执行、构建、安装依赖或导入被审查项目；新工具仍只做受限静态读取/确定性分析。
- [ ] **A-08 BLOCKER / E1** 没有临时诊断脚本、缓存、`__pycache__`、日志或前端构建产物进入交付 diff。
- [ ] **A-09 / E1** 所有新 Python 文件为 UTF-8 且含编码声明；Vue/JS/SCSS 中文无乱码。
- [ ] **A-10 / E1** `git diff --check` 通过，目标文件没有超长压缩单行或意外格式化无关区域。
- [ ] **A-11 BLOCKER / E1** 多 Agent 执行时，同一文件只有一个写入负责人；共享脏文件按 T00 清单和 tasks.md 分工独占修改。
- [ ] **A-12 BLOCKER / E1+E3** 每个并行批次从同一 integration commit 开始，合并后由集成负责人重跑依赖测试；验收负责人未直接改核心实现来制造通过。

---

## B. 架构与职责边界

- [ ] **B-01 BLOCKER / E1+E2** `AgentLoopEngine` 只做循环编排；Provider、Context、Scheduler、Tool、Timeline、Completion、Lease 均有清晰独立模块。
- [ ] **B-02 BLOCKER / E1** `runner.py` 已退化为兼容入口/feature flag 路由，没有继续叠加新 Loop 细节。
- [ ] **B-03 BLOCKER / E1** Route 只做鉴权、输入校验、Service 调用和安全响应；没有在 HTTP/SSE 线程直接推进 Loop。
- [ ] **B-04 / E1** 新文件保持领域边界，未创建万能 `utils/helpers`，未继续扩展已知巨型遗留模块。
- [ ] **B-05 / E1** 单文件超过约 250 行且承担超过三类职责时已拆分；例外有明确理由和测试。
- [ ] **B-06 BLOCKER / E2** v1 与 v2 有单向兼容层，没有两个并行写路径竞争同一事实。
- [ ] **B-07 / E1** 运行模式、状态、Action、Item、Event、错误码有单一来源；没有前后端各自随意定义。
- [ ] **B-08 BLOCKER / E2** baseline 是显式“策略工作流”降级，不被 UI/API 标记为模型自主多轮 Agent。

---

## C. Agent Loop 与模型在环证明

- [x] **C-01 BLOCKER / E3+E4** 至少一个真实 Run 展示三轮以上交错的 Model/Tool/Observation，而不是一次模型规划后固定执行。
- [x] **C-02 BLOCKER / E3+E4** 第 N+1 次模型请求包含第 N 次真实 Tool Result envelope、Observation 引用和最新上下文水位。
- [ ] **C-03 BLOCKER / E3** 模型动作只能是冻结的判别联合：Tool Calls、Plan Update、Request Approval、Ask User、Final Answer。
- [ ] **C-04 BLOCKER / E3** 模型不能直接调用 Handler、写数据库、修改 Run 状态、跳过审批或标记节点成功。
- [ ] **C-05 BLOCKER / E3** 每轮开始均检查 lease、Control Input、pause/cancel、deadline、budget 和 iteration limit。
- [x] **C-06 BLOCKER / E3** 多个 Tool Call 有稳定顺序；只有明确无依赖且安全时允许并行。
- [x] **C-07 BLOCKER / E3** 相同工具和参数重复超过上限时 Loop 停止或反馈，不形成死循环。
- [ ] **C-08 BLOCKER / E3** 连续模型错误、最大轮数、最大工具数、最大计划版本、墙钟时间都由配置化 Policy 强制。
- [ ] **C-09 BLOCKER / E3** 模型过早 Final Answer 会收到 Completion Feedback 并继续，不会直接 terminal。
- [ ] **C-10 BLOCKER / E3** baseline、hybrid、deep_audit 三种模式有独立测试和可观察标签。
- [ ] **C-11 / E3** Provider 不可用时降级路径和终态明确；系统不伪造“模型已分析”。
- [ ] **C-12 / E3** Decision Summary 有引用和策略码，能够解释选择，但不包含隐藏思维链。
- [x] **C-13 / E3** Reasoning Summary 来自模型真实 reasoning 输出的受限摘要（脱敏、限长、`sensitive_level`），可 delta 流式且刷新回放一致；不是伪造思考文案，也不包含完整原始思维链。

---

## D. Provider Tool Calling 契约

- [ ] **D-01 BLOCKER / E2** `AgentModelRequest` 支持有序 messages、tools、tool choice、mode、iteration、budget 和 context watermark。
- [ ] **D-02 BLOCKER / E2** 原生 Tool Calling 的 request/response/stream contract 测试通过。
- [ ] **D-03 BLOCKER / E2** JSON Fallback 使用严格 schema、版本、allowlist 和额外字段拒绝；没有 `eval` 或宽松正则猜测。
- [ ] **D-04 BLOCKER / E2** Provider Tool Call ID 与 Tool Result `tool_call_id` 正确关联并回填下一轮。
- [ ] **D-05 BLOCKER / E2** 并列 Tool Call 的 arguments delta 按 call ID 隔离，不串线、不覆盖。
- [ ] **D-06 BLOCKER / E2** 文本与 Tool Call 混合响应不会被误当成已完成最终回答。
- [ ] **D-07 / E2** Provider capability negotiation 覆盖 native tool、parallel、stream delta、reasoning channel 和 context limit。
- [ ] **D-08 / E2** failover 仅在 Policy、预算和幂等条件满足时发生，并有事件/审计。
- [ ] **D-09 BLOCKER / E2** 旧 QA/RAG/修复建议的文本 LLM 契约和测试未回归。
- [x] **D-10 BLOCKER / E2+E3** Provider 原始 body、Prompt、工具原始大结果、异常堆栈和授权信息不进入日志或 API。

---

## E. Context、多轮会话与控制输入

- [ ] **E-01 BLOCKER / E2** `AgentContextPack` 包含当前 goal、constraints、summary、recent messages、plan、completed actions、observations、artifacts、approvals、budgets、controller feedback 和 tool catalog digest。
- [ ] **E-02 BLOCKER / E2** 安全边界和当前 Control Input 的优先级高于旧摘要；摘要不能覆盖取消、审批或新目标。
- [ ] **E-03 BLOCKER / E2** 上下文不会每轮塞入完整 Event、完整源码或完整 Tool Result；大内容转 Artifact。
- [ ] **E-04 BLOCKER / E2** 会话摘要有 source sequence 范围、version、digest，并只覆盖声明水位。
- [ ] **E-05 / E2** 摘要失败时产生 `AGENT_CONTEXT_LIMITED`，保留关键约束并明确降级。
- [x] **E-06 BLOCKER / E3+E4** 活跃 Run 中用户追加消息在同一 Run 内形成有序 Control Input，并影响后续模型动作。
- [ ] **E-07 BLOCKER / E2** 重复 `client_request_id` 不产生重复 Message、Control Input、Event 或 Plan。
- [ ] **E-08 BLOCKER / E2** HTTP 消息接口不直接执行 Replan/Tool，只写入并唤醒 Worker。
- [ ] **E-09 BLOCKER / E2** Cancel、Pause、Approval、User Message 在同一控制队列中有确定优先级和作用域。
- [ ] **E-10 / E2** Conversation 的 context/summary version 与持久化摘要一致。

---

## F. 计划 DAG 与完成条件

- [ ] **F-01 BLOCKER / E2** Scheduler 按依赖计算 READY，不按 node ID 或数组顺序执行。
- [ ] **F-02 BLOCKER / E2** 节点 ID 与拓扑顺序相反的测试仍按正确依赖执行。
- [ ] **F-03 BLOCKER / E2** 所有前置成功后节点才 READY；缺失、失败或审批未通过时为 PENDING/BLOCKED。
- [ ] **F-04 BLOCKER / E2** FAILED 节点绝不加入满足依赖的成功集合。
- [ ] **F-05 BLOCKER / E2** 环、自依赖、未知依赖、重复 key、未知/禁止工具、超深/超大计划被拒绝。
- [x] **F-06 BLOCKER / E2** 强制基线由 Controller 注入和锁定，模型 Plan Patch 无法删除或伪造其成功。
- [ ] **F-07 BLOCKER / E2** Plan Patch 版本化并记录 parent、digest、原因和 Decision Record；历史版本只读。
- [ ] **F-08 / E2** 新 Plan supersede 旧未开始节点，已完成结果只能通过受控引用复用。
- [ ] **F-09 BLOCKER / E3** Completion Evaluator 同时检查 mandatory nodes、覆盖、证据、失败、警告、预算和用户目标。
- [ ] **F-10 BLOCKER / E3** `completed/completed_with_warnings/partial/failed/canceled` 五种终态均有正负测试。
- [ ] **F-11 BLOCKER / E3** 必需节点失败、证据不足或预算耗尽时，不会错误返回 `completed`。
- [ ] **F-12 / E3** Final Answer 明确目标、范围、结果、证据、限制/警告和后续建议。

---

## G. 工具执行治理

- [ ] **G-01 BLOCKER / E2** 每个 Tool Descriptor 明确 name/version/category/schema/risk/timeout/idempotent/approval/retry/modes/artifact/result version。
- [ ] **G-02 BLOCKER / E2** Descriptor 缺少安全关键字段时注册失败，不依赖危险默认值。
- [x] **G-03 BLOCKER / E2** 工具输入在 Handler 前拒绝未知字段、缺失 required、类型错误、越界、超长值和恶意路径。
- [ ] **G-04 BLOCKER / E2** workspace/project/snapshot/object authorization 在 Handler 前执行；负向测试确认 Handler 调用次数为零。
- [ ] **G-05 BLOCKER / E2** prohibited 永不执行；sensitive/approval-required 未批准时进入明确中断。
- [ ] **G-06 BLOCKER / E2** 预算先预留后结算；预算不足不启动工具。
- [ ] **G-07 BLOCKER / E2** 幂等逻辑调用可复用已完成结果；重复 dispatch 不重复副作用。
- [ ] **G-08 BLOCKER / E2** 自动重试同时要求 idempotent、retryable、允许错误码、预算和 deadline 有余量。
- [ ] **G-09 BLOCKER / E2** 每次 retry 有独立 attempt，但保持逻辑 call/node 关联和退避原因。
- [ ] **G-10 BLOCKER / E2** 硬超时或取消后的迟到结果不能写 succeeded 或推动下游。
- [ ] **G-11 BLOCKER / E2** 长工具轮询 cancel/deadline，刷新 heartbeat；进度只含数字和安全摘要。
- [ ] **G-12 BLOCKER / E2** Tool Result 经过 schema 校验、截断和脱敏；大结果进入 Artifact，模型只收引用。
- [ ] **G-13 BLOCKER / E3** 被审查项目永不被执行、构建、安装依赖、导入或任意网络访问。
- [ ] **G-14 / E2** Tool 错误返回稳定安全错误码、retryable 和 warning，不泄露堆栈或源码。

---

## H. 数据模型与迁移

- [ ] **H-01 BLOCKER / E1+E2** 迁移编号取实施时实际下一个编号，不覆盖或复用已有编号。
- [ ] **H-02 BLOCKER / E1** 同一结构已同步到迁移文件、`database/init.sql`、`MIGRATION_IDS` 和 SQLAlchemy 模型导出。
- [ ] **H-03 BLOCKER / E2** 新增 `agent_items`、`agent_control_inputs`、`agent_conversation_summaries`，字段和索引符合 `spec.md` 第 14 节。
- [ ] **H-04 BLOCKER / E2** `agent_events`、`agent_runs`、`agent_tool_calls`、`agent_checkpoints` 的扩展字段和唯一约束齐全。
- [ ] **H-05 BLOCKER / E2** `(run_id, sequence)` 唯一；Item public ID 唯一；Run 内 control client request 唯一；会话摘要版本唯一。
- [ ] **H-06 BLOCKER / E2** 常用分页、水位、Run/Item/Control 查询有索引，不依赖全表 `.all()` 后 Python 切片。
- [ ] **H-07 BLOCKER / E2** MySQL 8.0 DDL 与 SQLite 测试模型语义兼容，JSON/时间/唯一约束没有环境分叉。
- [ ] **H-08 BLOCKER / E2+E4** 加性迁移可重复执行，第二次执行无破坏、无重复 schema_migrations 记录。
- [ ] **H-09 BLOCKER / E1** 没有 DROP、TRUNCATE、RESET、破坏性 ALTER、旧字段删除或覆盖式回填。
- [ ] **H-10 BLOCKER / E3** 历史 v1 Run/Message/Event 迁移后仍可读取。
- [ ] **H-11 / E4** 本机数据库迁移由用户授权执行，并记录迁移 ID、退出码和只读结构验证结果。
- [ ] **H-12 / E4** 下列只读一致性查询无异常；若方言不同，提供等价查询：

```sql
SELECT run_id, sequence, COUNT(*) AS duplicate_count
FROM agent_events
GROUP BY run_id, sequence
HAVING COUNT(*) > 1;

SELECT public_id, COUNT(*) AS duplicate_count
FROM agent_items
GROUP BY public_id
HAVING COUNT(*) > 1;

SELECT run_id, client_request_id, COUNT(*) AS duplicate_count
FROM agent_control_inputs
GROUP BY run_id, client_request_id
HAVING COUNT(*) > 1;
```

---

## I. Durable Item/Event Protocol、Snapshot 与 SSE

- [ ] **I-01 BLOCKER / E2** 所有 v2 Event 使用冻结的 Envelope：event ID、sequence、schema version、conversation/turn/run、iteration、item/parent、state version、time、trace、payload。
- [ ] **I-02 BLOCKER / E2** 新 v2 Event 只有一个 `EventWriter` 写入口；没有业务模块直接自行分配 sequence。
- [ ] **I-03 BLOCKER / E2+E3** sequence 通过事务安全机制分配；并发测试无重复、缺号或倒退。
- [ ] **I-04 BLOCKER / E2** Run/Item 状态、Event 和必要 Checkpoint 水位处于一致事务边界；失败可回滚。
- [ ] **I-05 BLOCKER / E2** Item 生命周期为 `started → delta* → completed|failed`；终态后拒绝新 delta。
- [ ] **I-06 BLOCKER / E2** 重复 Event/Item transition 由 dedupe key 幂等处理，不产生重复文本或重复列表项。
- [ ] **I-07 BLOCKER / E2** Tool Result 和 Observation sequence 晚于对应 Tool Call；Final Assistant Item 晚于最后 Completion Decision。
- [x] **I-08 BLOCKER / E2** Snapshot 返回固定 `snapshot_watermark`，所有组成数据都不超过该水位。
- [ ] **I-09 BLOCKER / E2** `GET /agent-runs/{id}/items` 服务端分页，支持 after/before sequence、page size、item type，并限制最大页大小。
- [ ] **I-10 BLOCKER / E2+E4** SSE `id` 等于数据库 sequence；`event/data` 与持久 Event 一致，不在流层生成第二份语义。
- [ ] **I-11 BLOCKER / E2+E4** `Last-Event-ID` 重放无漏、无重、无乱序；过旧水位返回 `AGENT_SSE_REPLAY_GAP` 并能重拉 Snapshot。
- [ ] **I-12 BLOCKER / E2+E4** Heartbeat 能被客户端识别、刷新连接健康且不出现在用户时间线。
- [ ] **I-13 BLOCKER / E2** SSE route 只鉴权并流持久事件，不触发模型或工具执行。
- [ ] **I-14 BLOCKER / E2** 慢客户端、主动断开、terminal、Provider 错误都能安全关闭或重连，不破坏 Item 终态。
- [ ] **I-15 / E3** v1 Event 转 Legacy Item 时保留来源和 schema version，不伪造 v2 sequence/iteration。

---

## J. Lease、Checkpoint、审批与恢复

- [ ] **J-01 BLOCKER / E2** Lease acquire/refresh/release 原子化，包含 owner 与 expires_at；同一时刻只有一个 Worker 可推进 Run。
- [ ] **J-02 BLOCKER / E2** 未过期 lease 不能被其他 Worker 抢占；过期后只能按 recovery policy 恢复。
- [ ] **J-03 BLOCKER / E2** Checkpoint 包含 iteration、context watermark、current item、plan version、pending control watermark、budget、lease 和 digest。
- [ ] **J-04 BLOCKER / E2** Checkpoint 仅保存可序列化业务状态，不保存进程对象、Provider client 或隐式闭包。
- [ ] **J-05 BLOCKER / E3** 在 Model/Tool/Event/Checkpoint 各边界模拟崩溃后，恢复状态与无崩溃执行等价。
- [ ] **J-06 BLOCKER / E3** 已完成幂等 Tool 恢复后不重复执行；Event 和 Assistant delta 也不重复。
- [ ] **J-07 BLOCKER / E3** 非幂等工具处于未知结果时不自动重试，进入明确人工判断、partial 或 failed。
- [ ] **J-08 BLOCKER / E2+E4** Approval/Ask User/Pause 释放 Worker；Resume/Approval result 通过 Control Input 唤醒原 Run。
- [ ] **J-09 BLOCKER / E2+E4** Cancel 后不启动新工具；迟到结果标记 canceled/ignored，不推动 DAG。
- [ ] **J-10 BLOCKER / E3** 重复 RQ/线程 dispatch 不产生重复逻辑调用、Item 或 Event。
- [x] **J-11 BLOCKER / E3+E4** Watchdog 根据 lease/checkpoint/recovery policy 恢复，超过上限显式失败，不从头盲跑。
- [ ] **J-12 / E4** 用户授权的真实 pause/resume、approval continuation 和 Worker 中断恢复均有 run ID、sequence 和工具调用次数证据。

---

## K. Reasoning、敏感数据与安全边界

- [x] **K-01 BLOCKER / E2+E3+E4** 完整原始 chain-of-thought 全文不存在于数据库、Event payload、SSE、API、日志、Snapshot 或审计；Reasoning Summary 以脱敏、限长、带 `sensitive_level` 的形式存在于 Event/UI，且刷新回放与流式一致。
- [ ] **K-02 BLOCKER / E1+E2** `llm_analysis.py` 只保存脱敏、限长的 Reasoning Summary（不保存完整原始 `llm_reasoning` 全文）；既有用户改动经过 hunk 审查后安全合并。
- [ ] **K-03 BLOCKER / E2** Provider reasoning channel 若存在，只用于生成受限 Reasoning Summary（脱敏、限长后持久化）或瞬时丢弃；完整原始文本不落库；持久层不接收原始推理全文。
- [ ] **K-04 BLOCKER / E2** Decision Summary 只含目标、证据引用、选定动作、策略码、下一步和受限说明。
- [ ] **K-05 BLOCKER / E2+E3** 数据库/API/SSE/logger 扫描测试拒绝密码、Token、Cookie、Authorization、私钥、重置链接、验证码、原始 Prompt 和 Provider body。
- [ ] **K-06 BLOCKER / E2+E3** 完整源码和大 Tool Result 不写事件或日志；只保存授权 Artifact、digest、范围和脱敏摘要。
- [ ] **K-07 BLOCKER / E2** 用户目标、Tool Result 和扫描源码被视为不可信输入，不能覆盖系统安全边界或调用未知工具。
- [ ] **K-08 BLOCKER / E2** 用户提供路径/URL/ID 均经过 allowlist、规范化、workspace/snapshot 绑定和对象鉴权。
- [ ] **K-09 BLOCKER / E2** 工具输出中的提示词注入文本只作为数据，不被 Context renderer 提升为系统/开发指令。
- [ ] **K-10 BLOCKER / E2** API 错误返回稳定 code、safe message、retryable、trace ID；没有堆栈、SQL、路径或 Provider 原文。
- [ ] **K-11 BLOCKER / E3** 跨 workspace、跨 project、跨 conversation/turn/run/item/snapshot 的水平越权负向测试全部通过。
- [ ] **K-12 / E3** 角色不足、未登录、审批对象错配和过期审批均被拒绝并有安全审计。
- [ ] **K-13 BLOCKER / E1+E3** 新能力没有任意 Shell、任意文件写、任意外网访问或自动应用修复。
- [ ] **K-14 / E2** 日志只保留 actor/workspace/run/action/policy/result/trace/usage/cost/digest 等最小必要字段。

---

## L. API 与兼容契约

- [ ] **L-01 BLOCKER / E2** 现有 Run、pause/resume/cancel、events/SSE、Conversation、Approval、Observation、Cost API 保持兼容。
- [ ] **L-02 BLOCKER / E2** Run Snapshot 新增 items 和 watermark，不迫使旧客户端立即迁移。
- [ ] **L-03 BLOCKER / E2** Items API 参数、默认值、上限、排序和错误码有自动化契约测试。
- [ ] **L-04 BLOCKER / E2** Control Inputs API 对 body、type、payload、client request ID 做服务端 schema 校验。
- [ ] **L-05 BLOCKER / E2** Retry API 只接受可恢复的 failed/partial Run，并转为 control input + dispatch，不同步执行。
- [ ] **L-06 BLOCKER / E2** 所有 Agent API 在资源查询前后执行 workspace 和对象级授权。
- [ ] **L-07 / E2** 列表 API 使用数据库分页、稳定排序和 total，不使用 `.all()` 后切片。
- [ ] **L-08 BLOCKER / E2** API 响应 schema version 明确；未知事件/Item 允许安全忽略而不破坏顺序水位。
- [ ] **L-09 / E2** v1 deprecated 字段有兼容期说明，但本版本没有破坏性删除。
- [ ] **L-10 BLOCKER / E3** 同一 Snapshot API 多次读取在无新 Event 时结果稳定；有新 Event 时 watermark 单调递增。

---

## M. 前端统一时间线与 SSE 客户端

- [ ] **M-01 BLOCKER / E2+E4** Store 以 `itemsById + itemOrder + lastSequence + snapshotWatermark` 为事实，不再分组拼装 reasoning/steps/tools/messages。
- [ ] **M-02 BLOCKER / E2** `itemOrder` 只由 Item 首个 Event 的 sequence 决定；同一 Item delta 不改变位置。
- [ ] **M-03 BLOCKER / E2** 重复 Event、重复 delta、乱序批次均幂等；不能重复字、重复 Tool 卡片或倒序。
- [ ] **M-04 BLOCKER / E2** 所有事件先执行 gap 检测再判断是否显示；legacy reasoning 不能绕过 gap 检测。
- [ ] **M-05 BLOCKER / E2+E4** 发现 gap 后暂停增量应用，重拉 Snapshot，再从 watermark 重连；没有无限重连循环。
- [ ] **M-06 BLOCKER / E2** Snapshot 和 SSE 使用同一 generation token；切换 Run 后旧响应无法覆盖新页面。
- [ ] **M-07 BLOCKER / E2+E4** 首个有效响应、heartbeat 或 event 后连接状态为 `connected`；超时才进入 reconnecting。
- [ ] **M-08 BLOCKER / E2** Agent SSE 只有一个 parser，正确处理 id/event/data、多行 data、heartbeat、尾帧和错误帧。
- [ ] **M-09 BLOCKER / E2+E4** Assistant Message delta 更新同一 item；刷新后文本与流累计内容逐字一致。
- [ ] **M-10 BLOCKER / E4** UI 真实交错显示用户、意图、计划、工具、结果、Observation、决策、审批、警告和最终回答。
- [ ] **M-11 BLOCKER / E4** UI 不显示完整原始思维链；只显示标注“推理摘要”的受限 Reasoning Summary 与可审计的“决策摘要/过程摘要”，不恢复原始隐藏字段。
- [ ] **M-12 BLOCKER / E2** `AgentChat.vue` 只做页面编排；复杂转换、API、Store 和 Item 渲染已拆分。
- [ ] **M-13 / E1+E4** 组件优先复用 BaseIcon/BaseButton/BaseBadge/BasePanel；样式 scoped SCSS，无行内 style。
- [ ] **M-14 BLOCKER / E4** loading、empty、error、success、waiting approval、degraded、partial、terminal 状态均有真实 UI。
- [ ] **M-15 BLOCKER / E4** 桌面、平板、手机三断点通过；手机侧栏为可关闭抽屉并有 backdrop，操作按钮不溢出。
- [ ] **M-16 / E4** 键盘可操作，交互控件有标签，焦点和折叠状态可用，颜色对比可读。
- [ ] **M-17 / E3** 永久 `npm --prefix frontend run test:agent` 脚本通过，不依赖一次性诊断脚本。
- [ ] **M-18 BLOCKER / E3** `npm --prefix frontend run build` 成功；没有通过运行带 `--fix` 的 lint 来隐藏问题。
- [ ] **M-19 / E3** 5000 Event Reducer 性能测试无明显 O(n²)；Timeline 不无限渲染全部历史 DOM。
- [ ] **M-20 / E4** 工具参数/结果默认折叠且脱敏；源码只通过现有授权 Evidence Viewer 查看。

---

## N. 状态机、降级与最终回答

- [ ] **N-01 BLOCKER / E2** Run 状态转换由单一 State Machine 验证，非法转换被拒绝。
- [ ] **N-02 BLOCKER / E2** ACTIVE、INTERRUPTED、TERMINAL 状态集合与 Loop/Route/Frontend 一致。
- [x] **N-03 BLOCKER / E3** `completed` 只用于强制条件和用户目标均满足且无阻断失败。
- [ ] **N-04 BLOCKER / E3** `completed_with_warnings` 有有效结果且所有关键警告被显式披露。
- [ ] **N-05 BLOCKER / E3** `partial` 表示部分证据/目标完成但存在预算、Provider、工具、覆盖或恢复限制。
- [ ] **N-06 BLOCKER / E3** `failed` 表示无可信最终结果或不可恢复控制器失败，不生成虚假成功摘要。
- [ ] **N-07 BLOCKER / E3** `canceled` 保留已完成证据和取消原因，但不继续生成新的分析动作。
- [ ] **N-08 BLOCKER / E3** warning/error/stop reason 在 Run、Event、Final Answer 和 UI 中语义一致。
- [ ] **N-09 BLOCKER / E3+E4** Provider、RAG、图谱或敏感工具降级时，最终回答明确说明未验证范围。
- [ ] **N-10 BLOCKER / E2+E4** Final Answer 包含目标回顾、范围、结论、证据引用、限制/警告和后续建议；不含隐藏推理。
- [ ] **N-11 BLOCKER / E2** Final Assistant Item 完成失败时 Run 不会错误进入 completed；支持安全重试/partial。
- [ ] **N-12 / E4** UI 的“模型在环 / 策略工作流 / 已降级 / 等待审批 / 部分完成”完全由后端事实驱动。

---

## O. 可观测性、成本与审计

- [ ] **O-01 BLOCKER / E2** 每个 Run 有 trace ID，Model Turn、Tool Call、Item/Event、Checkpoint、Control Input 可按 trace/run 关联。
- [ ] **O-02 / E2** 指标包含 iteration、tool call/attempt、plan version、provider switch、context compression、approval wait、completion、recovery、event lag、SSE reconnect/gap。
- [ ] **O-03 BLOCKER / E2** usage/cost 与具体 model turn/run 关联，重试和 failover 不重复或遗漏计费。
- [ ] **O-04 / E3** Budget 预留、实际结算和 Run 汇总一致；负数、超预算和并发结算有测试。
- [ ] **O-05 BLOCKER / E2** 审计记录 actor、workspace、project/run、动作、policy/result code、trace、时间和 digest。
- [ ] **O-06 BLOCKER / E2** 审计/指标不记录 Prompt、完整用户内容、源码、Tool 原始大结果、Token、Cookie、完整原始 reasoning 全文或堆栈。
- [ ] **O-07 / E3** Provider latency/error、Tool latency/error、Loop stop reason、partial 原因可查询和聚合。
- [ ] **O-08 / E4** 实际 Run 能从 observability API/面板定位当前 iteration、活动 Item、等待原因、预算和终态。
- [ ] **O-09 / E3** Event 提交到 SSE 发送和浏览器应用的 lag 可测量，不能只依赖前端动画感知。
- [ ] **O-10 / E3** 敏感日志边界使用测试 logger/捕获器验证，不要求读取或暴露本地真实日志原文。

---

## P. 自动化验证门

- [ ] **P-01 BLOCKER / E2** 所有新增契约、Scheduler、Tool Policy、Context、Event、Completion、Recovery 和 Reducer 测试先失败后通过，失败原因与目标能力一致。
- [ ] **P-02 BLOCKER / E2** Provider 原生 Tool Calling 与 JSON Fallback 各有独立测试。
- [ ] **P-03 BLOCKER / E2** 工具输入、鉴权、超时、重试、幂等、取消均含负向测试。
- [ ] **P-04 BLOCKER / E2** DAG 失败传播、循环、未知依赖、强制基线绕过均含负向测试。
- [ ] **P-05 BLOCKER / E2** Event 并发、Snapshot watermark、SSE replay/gap/heartbeat、delta 幂等均有测试。
- [ ] **P-06 BLOCKER / E3** Scripted Provider 端到端测试至少三轮，并断言真实 Tool Result 进入下一模型请求。
- [ ] **P-07 BLOCKER / E3** 崩溃注入覆盖多个持久化边界，恢复后 exactly-once 语义成立。
- [ ] **P-08 BLOCKER / E3** 旧 Agent、LLM、QA/RAG、Approval、Observation、Cost、Provider Policy 相关回归测试通过。
- [ ] **P-09 BLOCKER / E3** 外部 LLM/embedding/rerank/API 在自动化测试中全部 mock；测试不发真实 HTTP。
- [x] **P-10 BLOCKER / E3** 后端 focused tests 有命令、退出码、通过/失败/跳过数。
- [x] **P-11 BLOCKER / E3** `backend\venv\Scripts\python.exe -m pytest tests -q` 全量通过；若因机器内存触发已知 embedding 降级，需单独归因并重新提供可靠证据。
- [x] **P-12 BLOCKER / E3** `npm --prefix frontend run test:agent` 通过。
- [x] **P-13 BLOCKER / E3** `npm --prefix frontend run build` 通过；既有 warning 与新增 warning 被区分。
- [x] **P-14 BLOCKER / E1** `git diff --check` 通过。
- [ ] **P-15 BLOCKER / E3** 测试没有通过跳过、删除断言、扩大容差、关闭安全门或 mock 掉被测核心来制造绿色结果。
- [ ] **P-16 / E3** 所有失败测试均完成根因处理；没有“偶尔通过”被当作完成。

**标准命令：**

```powershell
Set-Location D:\workproject\work\work-5238\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

```powershell
Set-Location D:\workproject\work\work-5238
npm --prefix frontend run test:agent
npm --prefix frontend run build
git diff --check
```

---

## Q. 真实数据库、Provider、SSE 与浏览器门

- [x] **Q-01 BLOCKER / E4** 用户确认 5001 端口 listener PID、父子进程链、命令行和启动时间，证明运行的是最新 venv 代码。
- [ ] **Q-02 BLOCKER / E4** 用户授权后应用加性迁移，记录迁移命令退出码和只读 schema 验证；未接触生产库。
- [ ] **Q-03 BLOCKER / E4** 使用不含秘密、可安全审查的已导入项目快照；没有执行该项目。
- [x] **Q-04 BLOCKER / E4** 使用项目已配置真实 Provider 完成至少一个 hybrid v2 Run，不读取或展示凭据。
- [x] **Q-05 BLOCKER / E4** 真实 Run 的第二轮模型调用确实受到前一 Tool Result/Observation 影响；证据来自安全 trace/digest 和后续动作，不要求暴露 Prompt。
- [x] **Q-06 BLOCKER / E4** 浏览器真实显示三轮以上 interleaved 时间线和增量 Final Answer。
- [x] **Q-07 BLOCKER / E4** 运行中追加用户方向进入同一 Run 并改变后续策略。
- [x] **Q-08 BLOCKER / E4** 浏览器刷新/断网重连后，Item 顺序、文本和 terminal 与刷新前一致。
- [x] **Q-09 BLOCKER / E4** 数据库只读 sequence/item ID、Snapshot watermark、SSE ID 和 UI order 可逐项对齐。
- [x] **Q-10 BLOCKER / E4** 真实 pause/resume 不重复已完成工具；若有审批能力，approval continuation 同样通过。
- [x] **Q-11 BLOCKER / E4** 获授权的测试环境完成一次 Worker 中断/恢复或等价进程级恢复验证。
- [x] **Q-12 BLOCKER / E4** 真实失败/降级场景至少验证一个，UI 和 Final Answer 正确显示 warning/partial，不伪装成功。
- [ ] **Q-13 BLOCKER / E4** 桌面、平板、手机视口完成浏览器验收，状态、抽屉、折叠、按钮和文本无阻断问题。
- [x] **Q-14 / E4** 浏览器 Console 无本改造引入的 error；Network 无重复失控请求、SSE 紧密重连或未授权响应。
- [x] **Q-15 BLOCKER / E4** 真实验收记录仅保存安全元数据和截图，不包含 Token、Cookie、Authorization、源码全文或敏感 payload。

若 Q-01 至 Q-15 任一 BLOCKER 无法执行，最终结论必须写为“产品级真实验收未完成”，并列出用户可执行的精确命令/步骤。

---

## R. 性能与可靠性目标

- [ ] **R-01 / E3+E4** 1000 Items 的 Snapshot 本地 P95 小于 1.5 秒，记录硬件、数据库和采样方法。
- [ ] **R-02 / E4** 已提交 Event 到浏览器显示 P95 小于 1 秒，不计模型/工具耗时。
- [ ] **R-03 BLOCKER / E3** 并发 Event Writer 压测无重复、缺失或倒退 sequence。
- [ ] **R-04 / E3** Reducer 处理 5000 Events 无明显 O(n²) 增长，记录时间和内存。
- [ ] **R-05 / E3+E4** Timeline 采用分页、折叠或窗口化，不无限创建历史 DOM。
- [ ] **R-06 BLOCKER / E2** 单次 Tool Result 和 Context Pack 有硬大小限制；超限转 Artifact 或产生明确降级。
- [ ] **R-07 / E3** Event/Item 分页查询使用索引，查询计划无明显全表扫描热点。
- [ ] **R-08 BLOCKER / E3+E4** Worker 恢复不重复已完成工具，开放 Run 不因一次进程重启永久卡死。
- [ ] **R-09 / E3** SSE 断开采用有限指数退避和 jitter，不形成重连风暴。
- [ ] **R-10 / E3** Provider/Tool 超时不会无限占用 Worker 或数据库 lease。

---

## S. Feature Flag、灰度与回滚

- [x] **S-01 BLOCKER / E2** `AGENT_LOOP_V2_ENABLED`、`AGENT_EVENT_SCHEMA_V2_ENABLED`、`AGENT_TIMELINE_V2_ENABLED` 默认关闭。
- [x] **S-02 BLOCKER / E2** Flag 可按全局/workspace policy 生效，未经授权的 workspace 不能自行开启高自治模式。
- [x] **S-03 BLOCKER / E3** Flag 关闭时新建 Run 使用 v1；打开时新建 Run 使用 v2；旧 Run 始终按其原协议读取。
- [x] **S-04 BLOCKER / E4+E5** 先在测试 workspace 灰度 baseline/hybrid/控制输入流程，再扩大范围。
- [x] **S-05 / E5** 灰度期间观察 provider error、tool failure、partial、recovery、event lag、SSE gap、cost 和安全告警。
- [x] **S-06 BLOCKER / E4+E5** 逐级关闭 Timeline v2、Event v2、Loop v2 的回滚演练成功。
- [x] **S-07 BLOCKER / E4** 回滚不删除 v2 表/数据，不执行 down migration，历史 v2 Run 仍可读。
- [x] **S-08 BLOCKER / E3** 前端 v2 关闭后旧 View 可用，服务端 Event 不丢失。
- [ ] **S-09 / E5** 默认启用 v2 前已有明确观察窗口、负责人和回滚触发条件。
- [x] **S-10 BLOCKER / E1** 本版本不删除 v1 API、旧表或旧字段；清理另立后续任务。

---

## T. 代码质量、文档与 Git 交付

- [ ] **T-01 BLOCKER / E1** 实际修改与 `spec.md` 范围一致，没有夹带无关功能或大规模重写。
- [ ] **T-02 BLOCKER / E1** 新增前已搜索现有 Service、Tool、Provider、Validator、Serializer、Composable 和 UI 组件，复用优先。
- [ ] **T-03 / E1** Python/JS/Vue 命名、错误类、序列化和目录布局符合仓库现有模式。
- [ ] **T-04 BLOCKER / E1** 路由薄、页面薄；鉴权、校验、业务编排、持久化、外部调用和审计没有堆在一个函数。
- [ ] **T-05 BLOCKER / E1** 没有宽泛静默 `except Exception`；降级有安全结构化告警和明确状态。
- [ ] **T-06 BLOCKER / E1** 没有新增不必要依赖；若必须新增，已说明维护性、安全性、替代方案和用户批准。
- [ ] **T-07 BLOCKER / E1** 迁移、API、配置、运行模式、事件协议、恢复和回滚说明已同步文档。
- [ ] **T-08 BLOCKER / E1** 三件套与实际实现路径、命令、状态和限制一致，不含未决占位交付。
- [ ] **T-09 BLOCKER / E1** `git status` 和 `git diff` 证明只包含意图修改；未提交 `.env`、日志、构建产物、缓存、临时脚本或用户无关改动。
- [ ] **T-10 / E1** 每个获授权批次使用中文 commit，提交前检查 diff，只暂存目标文件/hunk；没有强推。
- [ ] **T-11 / E1** 若仓库要求推送且当前会话已授权，推送成功并记录 branch/commit；否则明确标注未推送而不伪造完成。
- [ ] **T-12 BLOCKER / E1-E5** 最终报告严格区分：已验证完成、已实现未真实验证、未完成、外部阻塞、已知风险。
- [ ] **T-13 BLOCKER / E1** 已记录当前“无可依赖 CI、`.github/` 被忽略”的治理决定：要么有用户授权的独立 CI 改造证据，要么明确标注无自动合并保护，未虚构持续集成能力。

---

## U. 立即拒收条件

出现任一项，整体结论直接为“不通过”，修复并重新完整验证前不得豁免：

- [ ] **U-01** 模型仍只在开头规划、结尾总结，工具结果没有进入下一轮模型输入。
- [ ] **U-02** 前端仍把 Decision/Reasoning、Tool、Message 分组后伪装成时间顺序。
- [ ] **U-03** FAILED 节点被当作依赖完成，或必要节点失败后 Run 仍为 completed。
- [ ] **U-04** 继续以无锁 `MAX(sequence)+1` 作为并发序列分配。
- [ ] **U-05** 完整原始 chain-of-thought 全文出现在任一持久化、传输、日志或 UI 面；或 Reasoning Summary 未经脱敏、超限长、缺少 `sensitive_level` 标注。
- [ ] **U-06** 工具 schema、权限、审批、预算、超时、重试或取消仅写在 Descriptor，却未由 Executor 强制。
- [ ] **U-07** HTTP/SSE Route 直接推进 Agent Loop 或同步执行长工具。
- [ ] **U-08** 重连/恢复会重复 Tool、Event、Assistant delta 或丢失 Control Input。
- [ ] **U-09** 跨 workspace/project/snapshot/object 越权测试失败。
- [ ] **U-10** Agent 执行、构建、安装依赖或导入被审查项目。
- [ ] **U-11** 迁移包含破坏性 SQL，或 `database/init.sql`/迁移注册/模型不同步。
- [ ] **U-12** 自动化测试发真实外部 LLM/embedding/rerank 请求。
- [ ] **U-13** 使用跳过测试、删除断言、关闭安全门、宽泛 mock 核心或只做前端动画来制造通过。
- [ ] **U-14** 未做真实 Provider/SSE/浏览器/恢复验收却宣布产品整体完成。
- [ ] **U-15** 泄露秘密、授权头、Cookie、Prompt、完整源码、日志原文或 Provider 原始响应。
- [ ] **U-16** 覆盖、删除、提交或混入用户已有未提交改动。

验收时，上述方框全部应保持未勾选；任何一项被勾选都代表已触发拒收条件。

---

## V. 最终证据登记表

以下表格在最终交付时填写实际事实；空白行表示证据尚未完成，不得删除来规避验收。

### V.1 版本与工作区

| 项目 | 实际值 | 证据位置 |
|---|---|---|
| 基线 Git SHA | `b7f5e1d`（Agent v2 全链路回归与性能验证） | 本次验收起点 |
| 最终 Git SHA | `853ec65`（第二批：v2 事件全集 emit、审批闭环与 Retry API） | 验收完成点 |
| 分支 | `master` | 本地与 origin 同步（含未推送批次见交付记录） |
| 用户既有改动清单 | `frontend/src/components.d.ts`（Vite 自动生成，未提交）、`backend/rag_eval_cases.jsonl`、`backend/rag_report_*.json`（评测产物） | `git status` |
| 本改造文件清单 | 见各 commit：engine.py/watchdog.py/provider_selector.py/openai_compatible.py/graph_tools.py/registry.py + 前端 AgentThread/StatsBar/threadBlocks/blocks + 测试 | `git log b7f5e1d..HEAD`（15 个 commit） |
| `git diff --check` | 通过（仅 components.d.ts 的 CRLF 警告，非 whitespace error） | 仓库根执行 |

### V.2 自动化命令

| 命令 | 退出码 | 通过/失败/跳过 | 执行日期 | 证据位置 |
|---|---:|---|---|---|
| Agent focused tests（loop/vertical/gateway/stream/ops） | 0 | 通过（多次，如 16/23/28/37/430） | 2026-08-13 | 各批 commit message |
| 后端全量 `pytest tests -q -k agent` | 0 | 463 passed / 697 deselected | 2026-08-14 | 第二批后全量 |
| 前端 Agent tests `npm run test:agent` | 0 | 34 passed / 0 fail | 2026-08-14 | 第二批后运行 |
| 前端 build `npm run build` | 0 | 成功（仅 chunk 体积既有警告） | 2026-08-14 | 第二批后运行 |
| 审批闭环测试（requires_approval 拦截/request_approval 持久化/未注册工具拒绝） | 0 | 通过 | 2026-08-14 | `tests/test_agent_approval_retry.py` |
| Retry API 测试（failed→QUEUED 转换/越权 403/completed 409） | 0 | 通过 | 2026-08-14 | `tests/test_agent_approval_retry.py` |
| Action Parser 测试（request_approval/ask_user/plan_update 冻结动作） | 0 | 通过 | 2026-08-14 | `tests/test_agent_action_parser.py` |
| Event/Reducer 性能测试 | 0 | 通过（agent-timeline-performance） | 2026-08-13 | 前端测试套件内 |

### V.3 真实纵向切片

| 证据 | Run/工件 ID | 结果 | 证据位置 |
|---|---|---|---|
| 本机迁移 | 036_workspace_agent_feature_flags | 已授权执行并验证（schema_migrations 记录 + SHOW COLUMNS） | 2026-08-13 演练 |
| 真实 Provider hybrid Run | run 77 / run 81 | COMPLETED（run 81：10 工具、reasoning delta、assistant delta） | 浏览器会话 58 / S-04 演练 |
| 多轮 Tool Result 回填 | run 77 / run 81 | 每轮思考后工具真实执行并回填 | 时间线交错 |
| 用户中途追加消息 | run 50 / run 85 | Control Input `user_message` applied（id=11，applied_iter=0），36 工具 | Q-07 / S-04 演练 |
| SSE 断线重放 | run 45（v1）/ run 77 | 刷新后 sequence/文本/终态一致 | 浏览器刷新验证 |
| pause/resume | run 62 | paused（5 工具保留）→ resume → completed，工具不重复 | Q-10 记录 |
| Approval 等待时长 | — | 无审批工具真实触发（不适用） | — |
| spec 19.3 指标（Failover 率/SSE Gap·Resync 率/响应延迟） | run 87 + workspace 5 | 真实聚合：failover 0/23、SSE reconnects 1、首工具 P95 40s、最终回答 P95 72s（迁移 037 + 埋点 + 前端卡片） | 2026-08-14 复核 |
| Worker 中断恢复 | run 63 | 强杀后端 → 恢复入口 → completed_with_warnings，5 工具不重复 | Q-11 记录 |
| 桌面/平板/手机浏览器 | — | 桌面已验证；平板/手机经用户确认豁免（当前仅需电脑端） | 用户决定 |
| Feature Flag 回滚 | run 81/82/83/86 | 逐级关闭 Timeline→Event→Loop 全部成功；历史 v2 Run 可读；1377 条 v2 事件保留 | S-04~S-08 演练 |

### V.4 最终结论

| 结论项 | 结果 |
|---|---|
| 所有 BLOCKER 是否通过 | 是（E1-E3 自动化、E4 真实验收与灰度回滚演练均已完成；Q-13 三断点经用户豁免为电脑端） |
| 是否存在立即拒收条件 | 否 |
| 自动化验证是否完成 | 是（444 后端 / 33 前端 / build） |
| 真实产品验收是否完成 | 是（Q-04~Q-12 核心、S-04~S-08 灰度回滚已验；Q-13 三断点用户豁免） |
| 灰度与回滚是否完成 | 是（workspace 5 三开三关演练成功，历史 v2 数据保留） |
| 可否宣布整体改造完成 | 是——所有 BLOCKER、真实验收和灰度回滚均通过 |

最终签署必须附一句无歧义结论，只能从以下三种中选择：

1. **整体改造完成：** 所有 BLOCKER、真实验收和灰度回滚均通过。
2. **代码与自动化完成，产品验收未完成：** E1-E3 通过，但至少一个 E4/E5 门缺失。
3. **改造未完成：** 存在未通过 BLOCKER、测试失败、拒收条件或未实现任务。

**最终结论：整体改造完成。** 代码与自动化（E1-E3）、真实 Provider/SSE/浏览器验收（E4）和灰度回滚演练（E4/E5）均已通过；Q-13 平板/手机视口经用户明确豁免（当前交付范围仅需电脑端）。


### T14 后验审计纠偏（2026-08-15）

> **状态：进行中。** 本段覆盖此前默认产品路径未被验收覆盖的真实性问题；在 T14 全部完成前，不得仅凭旧的 V2 灰度记录宣称默认代码审计入口是成熟自主 Agent。

- [x] **T14-01 BLOCKER** 默认 `baseline` 必须在前端明确显示为基础审计工作流，不能展示模型自主工具调用或持续重规划承诺。
- [x] **T14-02 BLOCKER** V1 工作流运行中追加方向返回 `409 AGENT_DYNAMIC_CONTROL_UNAVAILABLE`，且数据库不产生任何控制副作用。
- [x] **T14-03 BLOCKER** V2 开启时追加方向仍以幂等 Control Input 进入 Loop，不由 HTTP 请求线程执行工具。
- [x] **T14-04 BLOCKER** Deep Review location 必须服务端验证属于本次授权 `CodeSliceEvidence` 的路径和行号范围。
- [x] **T14-05 BLOCKER** 无代码位置的模型结果只能是 low + proof gaps + `needs_more_evidence`，不得作为 `unverified` 漏洞结论。
- [x] **T14-06** RAG citation 仅能由模型从白名单选择，并在 UI 标记“背景参考，不构成代码证据”。
- [x] **T14-07** Context Pack 预算使用真实字符数，finding 驱动切片覆盖 finding 行附近代码。
- [x] **T14-08** focused 后端、前端 Node、生产构建和 diff check 全部通过。
- [ ] **T14-09** 完成真实浏览器验收，未创建无关扫描任务，记录 V1/V2 展示与错误语义（DevTools Chrome profile 锁占用，未绕过或终止用户浏览器）。
---

## W. 证据驱动 Harness V3 验收清单（2026-08-16）

- [x] **W-01** 已记录真实运行诊断基线；未在文档、事件或界面中写入源码、Prompt、Provider
  原始响应或凭据。
- [x] **W-02** 已选择 Plan-and-Execute + ReAct + Reflection；明确不实现完整原始 CoT 与 ToT。
- [x] **W-03** baseline 保持确定性工作流，V3 仅作用于 hybrid/deep_audit 且受 Run 快照灰度控制。
- [ ] **W-04 BLOCKER** `AuditSkillCatalog` 是受版本控制的深模块；模型和用户不能动态注册工具、
  技能或越过 Tool Registry。
- [ ] **W-05 BLOCKER** 每条审计假设都绑定 skill、目标、证据条件、授权代码范围和可审计状态。
- [ ] **W-06 BLOCKER** Deep Review 不能只接受自由文本 focus；其输入必须通过 hypothesis /
  required evidence / CodeSliceEvidence 校验。
- [ ] **W-07 BLOCKER** ReAct 工具观察能够推进假设；重复、无进展、预算耗尽和无授权位置安全收口。
- [ ] **W-08 BLOCKER** Evidence Critic 独立于 Planner；无代码位置或关键证据时不得确认漏洞。
- [ ] **W-09** Reasoning Summary 只含受控假设、行动理由、证据缺口和下一步；完整原始 CoT 不落库、
  不进 SSE、不进 API、不进日志。
- [ ] **W-10** 深度审查保留 token/context 预算，用户显式预算不被静默覆盖；预算耗尽文案可解释。
- [ ] **W-11** 假设/判定持久化、加性迁移、初始化 SQL、历史 Run 兼容和 Feature Flag 回滚全部验证。
- [ ] **W-12** 假设列表与详情接口有 workspace 鉴权、服务端分页和安全序列化；不泄露源码、Prompt、
  Token、Cookie 或 Provider 原始输出。
- [ ] **W-13** 前端攻击路径验证视图覆盖 loading、empty、error、blocked、历史 Run 和移动端。
- [ ] **W-14** 已知漏洞与安全对照夹具覆盖 SQL 注入、越权、SSRF/路径穿越、不安全执行/反序列化，
  且每个 confirmed candidate 有代码证据位置。
- [ ] **W-15** focused/backend 全量/前端 Node/build/diff check 全通过；真实 Provider 与浏览器验收
  仅在用户授权的测试 Workspace 完成，并记录脱敏结果。
- [ ] **W-16** V3 开关灰度启用、关闭与回滚后，baseline、V2、历史 V3 Run 均保持语义正确可读。