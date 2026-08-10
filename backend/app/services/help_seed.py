"""
帮助中心种子数据

按分类聚合 Markdown 文档原文，便于管理员编辑覆盖；首次启动时
由 `help_service.ensure_help_seed()` 幂等写入数据库。

内容规则：所有文档内容必须与代码实现一致，禁止虚构功能。
（依据 backend/app/services/scanners/、dependency_scanner.py、
 routes/oauth.py、routes/qa.py、services/security_knowledge.py 等源码核验）
"""
from __future__ import annotations

GETTING_STARTED_SLUG = "getting-started"

CATEGORY_SEED: list[dict] = [
    {
        "slug": "getting-started",
        "name": "快速入门",
        "description": "从注册登录到完成第一次安全扫描的最短路径。",
        "sort_order": 10,
    },
    {
        "slug": "feature-guide",
        "name": "功能指南",
        "description": "扫描能力、AI 安全助手与常见问题。",
        "sort_order": 20,
        "children": [
            {
                "slug": "faq",
                "name": "常见问题",
                "description": "关于支持范围、隐私与限制的官方答复。",
                "sort_order": 10,
            },
            {
                "slug": "scanning",
                "name": "扫描能力说明",
                "description": "支持的语言、检测规则与依赖审计。",
                "sort_order": 20,
            },
            {
                "slug": "ai-assistant",
                "name": "AI 安全助手",
                "description": "如何提问、引用来源与记忆机制。",
                "sort_order": 30,
            },
        ],
    },
    {
        "slug": "admin-manual",
        "name": "管理员手册",
        "description": "面向 teacher 与 admin 角色的治理与运维指南。",
        "sort_order": 30,
        "children": [
            {
                "slug": "knowledge-admin",
                "name": "安全知识库管理",
                "description": "知识源/文档的版本化、激活窗口与向量重建。",
                "sort_order": 10,
            },
        ],
    },
    {
        "slug": "troubleshooting",
        "name": "故障排查",
        "description": "常见问题的定位与处置清单。",
        "sort_order": 40,
    },
]


DOCUMENT_SEED: list[dict] = [
    {
        "category_slug": "getting-started",
        "slug": GETTING_STARTED_SLUG,
        "title": "快速开始",
        "summary": "注册登录、新建项目、上传代码、查看扫描结果，十分钟内完成第一次安全扫描。",
        "sort_order": 10,
        "content": """本指南带您完成从注册到看到第一份扫描结果的完整流程：**注册登录 → 新建项目 → 接入代码 → 等待扫描 → 阅读报告 → 询问 AI 助手**。

## 1. 注册与登录

1. 打开首页，点击「注册」，填写用户名（至少 6 位）、邮箱和密码（至少 6 位）即可完成注册，无需邀请码。
2. 除账号密码外，还支持 **Google 与 GitHub** 第三方登录。
3. 新注册账号为 `user` 角色，可在「个人中心」管理资料与偏好设置。

> 提示：若注册或登录时提示「请求过于频繁」，说明触发了限流保护（默认 10 次/分钟），稍等片刻再试。

## 2. 新建安全项目

1. 进入「安全项目」页面，点击「新建安全项目」。
2. 输入项目名称（建议与代码仓库名一致），回车确认。
3. 新项目状态为「待上传」，点击进入项目详情。

## 3. 接入代码

目前支持两种接入方式：

| 方式 | 说明 |
| --- | --- |
| **上传 ZIP 包** | 上传本地压缩包，系统做静态分析与依赖扫描 |
| **GitHub 导入** | 输入公开仓库地址 `https://github.com/{owner}/{repo}` 导入快照 |

ZIP 包限制（部署默认值，可在环境变量调整）：

- 仅支持 `.zip` 格式；
- 单包 ≤ 50 MB，解压后 ≤ 500 MB；
- 文件数 ≤ 20 000，目录嵌套 ≤ 10 层；
- 系统**不会执行**包内任何代码，仅做静态分析。

> 注意：GitHub 导入仅支持**公开仓库**，不执行 git 操作、不跟随重定向。

## 4. 等待扫描

- 项目状态依次流转：`待上传 → 校验中 → 快照中 → 扫描中 → 已完成`。
- 扫描完成（或完成但存在警告）后，即可查看报告。

## 5. 阅读报告

报告页提供：

1. **风险概览**：按严重度（严重/高危/中危/低危）聚合的漏洞分布。
2. **漏洞清单**：每条发现包含代码位置、规则编号（如 `PY-SHELL-TRUE`）与 CWE 分类。
3. **依赖清单**：解析出的依赖组件及其已知漏洞（需开启 OSV 依赖审计）。
4. **修复建议**：基于 LLM 生成的修复方案（需开启修复建议功能）。

## 6. 询问 AI 安全助手

- 在问答页输入自然语言问题，例如：「我的项目里有硬编码密钥的发现，怎么处理？」。
- 助手会结合当前扫描结果与安全知识库回答，并附引用来源（相似度与行号）。
- 问答接口默认限流 10 次/分钟/用户。

## 7. 进阶：Agent 工作台

对需要深度审计的项目，可在项目详情进入「Agent 工作台」：

- 输入审计目标（≤ 4000 字符），选择模式（`baseline` / `hybrid` / `deep_audit`）与预算；
- Agent 会按计划执行：生成快照 → 基线扫描 → 依赖盘点 → 覆盖率统计 → 风险排序 → 汇总报告；
- 任务可暂停、恢复、取消，进度通过事件流实时展示。

祝您使用愉快。
""",
    },
    {
        "category_slug": "faq",
        "slug": "faq-overview",
        "title": "常见问题",
        "summary": "关于扫描支持范围、数据隐私、角色权限与限流的官方答复。",
        "sort_order": 10,
        "content": """## 支持哪些语言和框架？

静态扫描支持 **Python、JavaScript/TypeScript、Java、Go** 四种语言，框架识别包括：

| 语言 | 识别的框架 |
| --- | --- |
| Python | Flask、Django |
| JavaScript / TypeScript | React、Vue、Angular、Express、Next.js |
| Java | Spring |
| Go | Gin、Echo、Fiber、Chi |

## 能检测哪些漏洞？

内置 **15 条确定性检测规则**，覆盖 9 个 CWE 类别，例如：

- 命令执行（`PY-SHELL-TRUE`、`JS-CHILD-PROCESS-EXEC`、`JAVA-RUNTIME-EXEC`、`GO-EXEC-SH`，CWE-78）
- 不安全反序列化（`PY-YAML-UNSAFE-LOAD`，CWE-502；`JAVA-OBJECT-INPUT-STREAM`，CWE-502）
- XSS（`JS-DANGEROUSLY-SET-INNER-HTML`，CWE-79）
- 弱加密（`GO-CRYPTO-MD5`，CWE-327）
- 硬编码凭据（`GENERIC-HARDCODED-SECRET`，CWE-798）

此外还有**机密扫描**：对所有文本文件按行匹配密钥赋值模式，命中后记录脱敏摘要与 SHA-256 指纹。

## 支持依赖漏洞审计吗？

支持。依赖扫描可解析以下清单文件：

- `requirements*.txt`、`pyproject.toml`（Python）
- `package.json`、`package-lock.json`（JavaScript）
- `pom.xml`（Maven）
- `build.gradle` / `build.gradle.kts`（Gradle）

已知漏洞查询对接 **OSV.dev**，且**默认关闭**（需部署时设置 `SCA_OSV_ENABLED=true`）。查询仅发送生态、包名与版本，不发送代码内容。

## 我的代码会被上传到第三方吗？

不会。系统只把代码用于本地静态分析；依赖审计联网时也仅发送包名/版本到 OSV.dev。自定义 LLM Provider 的密钥使用 Fernet 加密存储，并对回调地址做 SSRF 防护（私网拦截 + 主机白名单）。

## 有哪些角色？有什么区别？

平台预置四个角色：`admin`、`teacher`、`user`、`guest`。

- **admin**：拥有全部权限，可管理用户、知识库、帮助文档等。
- **teacher**：可创建/编辑/删除知识库内容，可评审问答。
- **user**：可提问、查看历史、收藏、管理个人记忆。
- **guest**：仅可浏览公开知识。

## 问答历史会保留多久？

系统**没有自动清理机制**，会话会一直保留，直到您在「问答历史」中手动删除。每次提问的上下文取自当前会话最近的 10 条记录。

## 为什么提示「请求过于频繁」？

问答接口默认限流 **10 次/分钟/用户**；登录/注册等接口有独立限流。这是部署默认值，可通过环境变量调整。

## 支持自定义大模型吗？

支持。在「LLM 配置」中可添加 OpenAI 兼容的 Provider（需提供 base_url 与 API Key），设为默认后问答与 Agent 均会使用。内置默认模型为通义千问（DashScope）与 MiniMax。

## 如何联系人工支持？

本帮助中心由管理员维护；遇到无法解决的问题，请提供项目 ID、复现步骤与日志片段（注意脱敏）联系系统管理员。
""",
    },
    {
        "category_slug": "scanning",
        "slug": "scanning-overview",
        "title": "扫描能力说明",
        "summary": "扫描器组成、检测规则清单、机密扫描与依赖审计的详细说明。",
        "sort_order": 20,
        "content": """## 一、扫描器组成

一次扫描由四类扫描器协作完成：

| 扫描器 | 职责 |
| --- | --- |
| 语言扫描器 | 对 Python / JS-TS / Java / Go 源码做确定性模式匹配 |
| 机密扫描器 | 对所有文本文件检测密钥赋值模式 |
| 依赖扫描器 | 解析依赖清单并生成依赖库存 |
| OSV 审计（可选） | 将依赖与 OSV.dev 漏洞库比对 |

## 二、语言扫描规则

### Python（`python-baseline`）

| 规则 | CWE | 描述 |
| --- | --- | --- |
| `PY-SHELL-TRUE` | CWE-78 | `subprocess` 等以 `shell=True` 执行命令 |
| `PY-YAML-UNSAFE-LOAD` | CWE-502 | 使用不安全的 `yaml.load` |
| `PY-FLASK-DEBUG` | CWE-489 | Flask 调试模式开启（`debug=True`） |

### JavaScript / TypeScript（`javascript-typescript-baseline`）

| 规则 | CWE | 描述 |
| --- | --- | --- |
| `JS-EVAL` | CWE-95 | 对不可信输入执行 `eval` |
| `JS-CHILD-PROCESS-EXEC` | CWE-78 | 使用 `child_process` 执行拼接命令 |
| `JS-DANGEROUSLY-SET-INNER-HTML` | CWE-79 | React `dangerouslySetInnerHTML` |
| `JS-CORS-WILDCARD` | CWE-942 | CORS 允许任意来源 |

### Java（`java-baseline`）

| 规则 | CWE | 描述 |
| --- | --- | --- |
| `JAVA-RUNTIME-EXEC` | CWE-78 | `Runtime.exec` 执行命令 |
| `JAVA-OBJECT-INPUT-STREAM` | CWE-502 | 直接反序列化对象输入流 |
| `JAVA-XXE-FACTORY` | CWE-611 | XML 解析未禁用外部实体 |
| `JAVA-CORS-WILDCARD` | CWE-942 | CORS 允许任意来源 |

### Go（`go-baseline`）

| 规则 | CWE | 描述 |
| --- | --- | --- |
| `GO-EXEC-SH` | CWE-78 | `exec.Command("sh", "-c", ...)` 执行命令 |
| `GO-CRYPTO-MD5` | CWE-327 | 使用 MD5 等弱哈希 |
| `GO-TLS-INSECURE` | CWE-295 | 跳过 TLS 证书校验 |

> 以上为**确定性规则**（静态模式匹配），不包含需要运行时的分析。规则数量与内容会随版本演进。

## 三、机密扫描

- 对所有文本文件按行匹配密钥赋值模式（如 `api_key = "..."`、`password: ...`）。
- 命中后不展示完整密钥，而是记录**脱敏摘要**与 **SHA-256 指纹**，便于定位与去重。
- 系统不执行任何代码，扫描结果仅保留在项目工作区内。

## 四、依赖扫描

支持的清单类型与优先级：

| 生态 | 清单文件 |
| --- | --- |
| Python | `requirements*.txt`、`pyproject.toml` |
| JavaScript | `package.json`、`package-lock.json` |
| Java | `pom.xml`（Maven） |
| Gradle | `build.gradle`、`build.gradle.kts` |

依赖审计（OSV）**默认关闭**；开启后每次扫描会把生态/包名/版本批量发送至 OSV.dev 比对已知漏洞（CVE）。

## 五、扫描策略与限制

- 扫描为**基线模式**：一次完成规则匹配与依赖盘点，无运行时沙箱。
- 排除规则：可在项目层配置排除目录/文件（如 `node_modules`）。
- 覆盖率记录：扫描完成后生成覆盖报告，列出每个文件是否被扫描。

## 六、明确不做的事

- 不执行任何用户代码（无沙箱运行）；
- 不做运行时行为分析（无动态污点跟踪）；
- 不上传代码到任何第三方分析服务。
""",
    },
    {
        "category_slug": "ai-assistant",
        "slug": "ai-assistant-guide",
        "title": "AI 安全助手使用指南",
        "summary": "如何提问、理解引用来源、使用记忆与反馈机制。",
        "sort_order": 30,
        "content": """AI 安全助手是 CyberGuard 内置的安全问答助手，回答会结合**当前项目扫描结果**、**公共知识库**（含安全知识治理中的文档）与**用户记忆**。

## 一、如何提问

好的提问包含足够的上下文：

> 我的项目扫描报出 `GENERIC-HARDCODED-SECRET`，文件在 `config.py`，请问该怎么处理？

提示：

1. 说明项目或模块名称，便于助手定位上下文；
2. 指明问题类型：修复方案、原因解释、影响面等；
3. 一次聚焦一个问题，避免多主题混杂。

## 二、理解回答与引用

- 助手回答会附带**引用来源**：来源文档、相似度与原文行号（如「第 12-18 行」）。
- 引用来自知识库检索（混合检索：语义 + 词法 + 知识图谱），并按相似度排序。
- 命中词法检索时相似度可能为空，属正常现象。

### 关于信任度

安全知识库的文档在入库时带有 `trust_score`（0.6 ~ 1.0），并由**引用注入检测**（`rag_guard`）过滤可疑内容：检测到角色注入（如 `<system>` 标签）、不可信区块等会直接标记/剔除，防止知识内容污染回答。

## 三、提问限制

- 问答接口默认限流 **10 次/分钟/用户**；
- 每次提问的上下文取当前会话最近 **10 条**记录；
- 对话记录**不会自动删除**，可随时在「问答历史」手动清理。

## 四、持久记忆（可选）

- 「持久记忆」默认关闭，可在问答设置中开启（`persistent_memory_enabled`）。
- 开启后，助手会从问答中提取事实、偏好、目标等**记忆条目**，后续提问时按相关性召回。
- 记忆支持**增删改查**：在「我的记忆」中查看、修改或删除单条记忆；已有相似记忆时不会重复写入（去重阈值 0.92），并按时间衰减降低旧记忆权重。
- 记忆与问答一样由模型提取，请勿在其中存放机密信息。

## 五、反馈与纠错

每条回答下方有 👍 / 👎 反馈按钮，反馈会写入反馈日志，供系统改进回答质量。

## 六、支持的快捷操作

| 操作 | 方式 |
| --- | --- |
| 发送消息 | `Enter` |
| 换行 | `Shift + Enter` |
""",
    },
    {
        "category_slug": "knowledge-admin",
        "slug": "knowledge-admin-guide",
        "title": "安全知识库管理",
        "summary": "面向 teacher / admin 的知识源与文档管理、生效窗口与向量索引重建。",
        "sort_order": 10,
        "content": """本文面向 **teacher / admin（平台角色）** 与 **owner / security_admin（工作区角色）**，介绍安全知识治理的完整流程。

## 一、模型

知识库分两层：

- **知识源（Source）**：一个来源（内部规范、公开报告等），含 `source_version`、激活开关与生效窗口。
- **知识文档（Document）**：挂在知识源下，含 `document_version`、摘要、正文、生效起止时间。

文档只有**在生效窗口内且激活**时，才会进入检索索引。

## 二、管理入口

进入「安全知识治理」页面：

1. **创建知识源**：填写名称、来源类型、版本号与描述。
2. **添加文档**：在知识源下创建文档版本，粘贴或上传 Markdown 正文。
3. **设置生效窗口**：通过 `effective_from` / `effective_until` 控制文档参与检索的时间段。
4. **激活/停用**：未激活的文档不会参与问答检索。

## 三、版本化

- 同一文档可存在多个版本，`document_version` 自增；
- 新版本默认未激活，需手动激活才会进入索引；
- 修改文档内容会新增版本，旧版本保留可追溯。

## 四、向量索引重建

更换 embedding 模型或维度后**必须**重建索引：

```bash
cd backend
venv\\Scripts\\flask.exe --app run reindex-knowledge
```

该命令会删除 `knowledge_embeddings` 与 `security_knowledge_embeddings` 两个向量集合并重新分块入库。重建期间问答检索能力会临时降级（只走词法检索）。

> 也可以在「LLM 配置 → 健康检查」中确认 embedding / rerank 服务状态。

## 五、检索与引用防护

- 检索使用混合策略：向量语义 + BM25 词法 + 知识图谱，结果按 RRF 融合、按文档去重；
- 每个文档块携带整文档行号（`start_line` / `end_line`），回答引用时给出「第 X-Y 行」；
- **引用注入检测**（`rag_guard`）会识别并剔除角色注入、不可信区块等可疑内容；
- 引用文档带 `trust_score`（0.6 ~ 1.0）与注入标记，前端会展示相似度（词法命中时为 None）。

## 六、权限与审计

- 知识库管理接口仅 `owner` / `security_admin` 工作区角色可写（平台 teacher / admin 拥有知识编辑权限）；
- 所有创建/更新/删除操作写入 `audit_events` 审计表（操作人、时间、变更前后）。

## 七、注意事项

- 知识库与 workspace 私有知识库边界独立，不得绕过 workspace 鉴权直接操作；
- 文档正文有大小上限（默认 100 000 字符）；
- 修改文档后若发现检索结果未更新，请检查文档是否在生效窗口内且已激活。
""",
    },
    {
        "category_slug": "troubleshooting",
        "slug": "troubleshooting-overview",
        "title": "故障排查",
        "summary": "扫描、上传、问答、登录等常见问题的定位与处置。",
        "sort_order": 10,
        "content": """## 1. 扫描长时间卡在「快照中」或「扫描中」

排查步骤：

1. 确认 ZIP 包符合限制：≤ 50 MB、解压 ≤ 500 MB、文件数 ≤ 20 000、嵌套 ≤ 10 层；
2. 检查是否包含大量二进制/图片文件（不影响扫描结果但会拖慢解压）；
3. 查看后端日志（默认 `backend/data/logs/app.log`）中的错误信息；
4. 若任务配置了重试仍失败，删除项目后重新上传，或联系管理员查看扫描任务状态。

## 2. 报告「依赖清单」为空

可能原因：

- 项目根目录缺少支持的清单文件（`requirements.txt`、`package.json`、`pom.xml`、`build.gradle` 等）；
- 依赖文件被排除规则忽略（检查「排除规则」配置）；
- 依赖扫描本身正常，但项目确无第三方依赖。

## 3. AI 助手回答异常（超时/截断/报错）

排查顺序：

1. **超时或重试**：LLM 调用默认重试 2 次（指数退避），检查是否最终恢复；
2. **模型不可用**：到「LLM 配置 → 健康检查」确认当前 Provider 与内置模型（DashScope / MiniMax）状态；
3. **自定义 Provider 失败**：检查 base_url 是否在 SSRF 白名单内、API Key 是否有效；
4. **上下文过长**：问答上下文取最近 10 条记录，过长时清理会话历史。

## 4. 登录/注册失败

| 现象 | 可能原因 |
| --- | --- |
| 401 用户名或密码错误 | 密码错误、账号被禁用 |
| 429 请求过于频繁 | 命中登录/注册限流（默认 10 次/分钟） |
| 500 服务器内部错误 | 数据库或配置异常，查看后端日志 |

## 5. 上传 ZIP 提示「路径不安全」

系统拒绝包含**绝对路径**或 `..` 跳级路径的压缩包条目。请重新打包并确认所有文件为相对路径。

## 6. 知识库检索质量下降

- 检查最近是否切换过 embedding 模型（切换后必须执行 `reindex-knowledge` 重建索引）；
- 确认文档在生效窗口内且已激活；
- 到「LLM 配置 → 健康检查」确认 embedding 服务在线；
- 若使用硅基流动 API，确认 `EMBEDDING_API_ENABLED` 与 Key 配置正确。

## 7. 数据与隐私相关

- 自定义 Provider 的 API Key 使用 Fernet 加密存储，仅保存密文与密钥指纹；
- 依赖审计仅在开启 `SCA_OSV_ENABLED` 时向 OSV.dev 发送包名/版本；
- 代码内容不会上传到任何第三方平台。

## 8. 仍然无法解决？

提交问题时请附上：

1. 项目 ID / 扫描任务 ID；
2. 复现步骤；
3. 后端日志相关片段（注意脱敏，不要包含密钥与 Token）；
4. 浏览器控制台报错截图。
""",
    },
]