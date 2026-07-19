# 基于智能问答的网络安全教学系统 - 项目规范

## 1. 项目概述

### 项目名称
CyberGuard - 网络安全智能问答教学系统

### 项目类型
Web应用系统（前后端分离架构）

### 核心功能概述
基于检索增强生成（RAG）与大语言模型（LLM）的智能问答系统，专注于网络安全领域的教学支持。系统通过融合向量语义检索与知识图谱关联检索，为用户提供精准、专业的智能问答服务。

### 目标用户
- 网络安全专业学生
- IT从业者
- 网络安全培训教师
- 企业安全培训部门

---

## 2. 技术架构

### 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Vue.js + Element)                    │
├─────────────────────────────────────────────────────────────────┤
│                      用户界面层 (UI Layer)                        │
│  - 登录注册    - 知识库管理    - 智能问答    - 个人中心           │
├─────────────────────────────────────────────────────────────────┤
│                        API网关层                                  │
│                    (Flask RESTful API)                           │
├─────────────────────────────────────────────────────────────────┤
│                      业务逻辑层                                   │
│  ┌──────────────┬──────────────┬──────────────┐                  │
│  │ 用户管理模块 │ 知识库管理   │ RAG问答引擎  │                  │
│  └──────────────┴──────────────┴──────────────┘                  │
├─────────────────────────────────────────────────────────────────┤
│                        数据层                                     │
│  ┌──────────────┬──────────────┬──────────────┐                  │
│  │   MySQL      │  向量数据库  │  知识图谱    │                  │
│  │  (结构化)    │  (ChromaDB) │  (NetworkX) │                  │
│  └──────────────┴──────────────┴──────────────┘                  │
├─────────────────────────────────────────────────────────────────┤
│                      LLM服务层                                    │
│                 (通义千问 Qwen API)                              │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈

#### 前端
- **框架**: Vue.js 3.x
- **UI组件库**: Element Plus
- **状态管理**: Pinia
- **HTTP客户端**: Axios
- **路由**: Vue Router 4.x
- **构建工具**: Vite

#### 后端
- **框架**: Flask 3.x
- **ORM**: SQLAlchemy
- **向量数据库**: ChromaDB
- **知识图谱**: NetworkX
- **LLM调用**: DashScope API (通义千问)
- **嵌入模型**: text2vec-base-chinese
- **Python版本**: 3.10+

#### 数据库
- **关系型数据库**: MySQL 8.0
- **配置**: 见 backend/config.py

---

## 3. 功能模块设计

### 3.1 用户管理模块

#### 功能列表
| 功能 | 描述 |
|------|------|
| 用户注册 | 支持邮箱/用户名注册，密码加密存储 |
| 用户登录 | 支持JWT令牌认证 |
| 个人信息 | 查看和修改个人资料 |
| 密码修改 | 修改登录密码 |
| 登录日志 | 查看历史登录记录 |

#### 用户权限
| 角色 | 权限说明 |
|------|----------|
| 游客 | 浏览公开问答，查看知识库目录 |
| 普通用户 | 提问、收藏、查看历史、反馈评价 |
| 教师 | 管理知识库、审核问答、管理学生 |
| 管理员 | 系统配置、用户管理、数据统计 |

### 3.2 知识库管理模块

#### 知识库结构
```
知识库 (Knowledge Base)
├── 知识分类 (Category)
│   ├── 网络基础
│   ├── Web安全
│   ├── 系统安全
│   ├── 密码学
│   ├── 渗透测试
│   └── 应急响应
└── 知识条目 (Knowledge Item)
    ├── 标题
    ├── 内容
    ├── 标签
    ├── 来源
    ├── 难度等级
    └── 相关知识点
```

#### 功能列表
| 功能 | 描述 |
|------|------|
| 知识分类 | 创建、编辑、删除知识分类 |
| 知识条目 | 添加、编辑、删除、上传知识条目 |
| 批量导入 | 支持Markdown、JSON格式批量导入 |
| 知识检索 | 全文检索、分类筛选 |
| 知识图谱 | 可视化展示知识点关联关系 |
| 知识统计 | 浏览量、收藏量、关联度统计 |

### 3.3 RAG智能问答引擎（核心模块）

#### 系统架构
```
用户问题 → 问题理解 → 查询构建
                          ↓
                    ┌─────┴─────┐
                    ↓           ↓
              向量检索      知识图谱检索
                    ↓           ↓
                    └─────┬─────┘
                          ↓
                    结果融合排序
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

#### 核心技术
1. **向量化检索**: 使用text2vec将文本转为向量，通过ChromaDB进行相似度检索
2. **知识图谱检索**: 基于NetworkX构建知识图谱，支持多跳推理检索
3. **混合检索融合**: 结合向量检索与图谱检索结果，通过RRF算法融合
4. **Prompt工程**: 设计专业的系统提示词，引导LLM生成高质量答案
5. **来源追溯**: 自动标注答案引用的知识来源

#### 功能列表
| 功能 | 描述 |
|------|------|
| 智能问答 | 输入自然语言问题，获取AI生成答案 |
| 多轮对话 | 支持上下文关联的连续对话 |
| 来源展示 | 显示答案引用的知识来源和置信度 |
| 追问建议 | 根据问题自动推荐相关追问 |
| 相似问题 | 推荐相似的历史问题及答案 |
| 反馈机制 | 用户可评价答案质量，持续优化 |

### 3.4 问答历史与收藏

#### 功能列表
| 功能 | 描述 |
|------|------|
| 历史记录 | 保存用户所有问答记录 |
| 收藏功能 | 收藏有价值的问答 |
| 搜索历史 | 快速查找历史问答 |
| 分享功能 | 生成分享链接 |

### 3.5 数据统计与可视化

#### 统计维度
- 用户活跃度统计
- 知识库热度分析
- 问答质量评估
- 系统性能监控

---

## 4. 数据库设计

### 4.1 ER图概述

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│   User   │──────<│  UserRole    │>──────│   Role   │
└────┬─────┘       └──────────────┘       └──────────┘
     │                                           │
     │ 1:N                                       │
     ↓                                           │
┌──────────────┐       ┌──────────────┐          │
│  QARecord    │>──────<│   Favorite   │          │
└────┬─────┘       └──────────────┘          │
     │                                           │
     │ N:1                                       │
     ↓                                           │
┌──────────────┐       ┌──────────────┐          │
│  Category    │──────<│KnowledgeItem │>─────────┘
└──────────────┘       └──────┬───────┘
                              │
                              │ N:M
                              ↓
                        ┌──────────┐
                        │   Tag    │
                        └──────────┘
```

### 4.2 主要数据表

#### users (用户表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 用户ID |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 |
| email | VARCHAR(100) | UNIQUE, NOT NULL | 邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| nickname | VARCHAR(50) | | 昵称 |
| avatar_url | VARCHAR(255) | | 头像URL |
| role_id | INT | FK | 角色ID |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | | 更新时间 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否激活 |

#### categories (知识分类表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 分类ID |
| name | VARCHAR(100) | NOT NULL | 分类名称 |
| description | TEXT | | 分类描述 |
| parent_id | INT | FK(self) | 父分类ID |
| icon | VARCHAR(50) | | 图标名称 |
| sort_order | INT | DEFAULT 0 | 排序 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

#### knowledge_items (知识条目表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 条目ID |
| title | VARCHAR(200) | NOT NULL | 标题 |
| content | TEXT | NOT NULL | 内容 |
| summary | TEXT | | 摘要 |
| category_id | INT | FK | 分类ID |
| difficulty | ENUM('easy','medium','hard') | | 难度 |
| source | VARCHAR(200) | | 来源 |
| author_id | INT | FK | 作者ID |
| view_count | INT | DEFAULT 0 | 浏览次数 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | | 更新时间 |

#### knowledge_tags (知识标签关联表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | ID |
| knowledge_id | INT | FK | 知识ID |
| tag_name | VARCHAR(50) | | 标签名 |

#### qa_records (问答记录表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 记录ID |
| user_id | INT | FK | 用户ID |
| question | TEXT | NOT NULL | 问题 |
| answer | TEXT | | 答案 |
| sources | JSON | | 来源信息 |
| confidence | FLOAT | | 置信度 |
| model_name | VARCHAR(50) | | 使用的模型 |
| response_time | FLOAT | | 响应时间(秒) |
| feedback | ENUM('good','neutral','bad') | | 用户反馈 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |

#### qa_conversations (问答会话表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 会话ID |
| user_id | INT | FK | 用户ID |
| title | VARCHAR(200) | | 会话标题 |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | | 更新时间 |

#### favorites (收藏表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | ID |
| user_id | INT | FK | 用户ID |
| qa_record_id | INT | FK | 问答ID |
| created_at | DATETIME | DEFAULT NOW | 收藏时间 |

#### login_logs (登录日志表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | ID |
| user_id | INT | FK | 用户ID |
| ip_address | VARCHAR(50) | | IP地址 |
| user_agent | VARCHAR(255) | | 用户代理 |
| login_time | DATETIME | DEFAULT NOW | 登录时间 |
| status | ENUM('success','failed') | | 登录状态 |

---

## 5. API接口设计

### 5.1 用户相关接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /api/auth/register | 用户注册 | 否 |
| POST | /api/auth/login | 用户登录 | 否 |
| POST | /api/auth/logout | 用户登出 | 是 |
| GET | /api/auth/me | 获取当前用户 | 是 |
| PUT | /api/auth/profile | 修改个人信息 | 是 |
| PUT | /api/auth/password | 修改密码 | 是 |

### 5.2 知识库相关接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | /api/categories | 获取知识分类列表 | 否 |
| POST | /api/categories | 创建分类 | 管理员 |
| PUT | /api/categories/{id} | 更新分类 | 管理员 |
| DELETE | /api/categories/{id} | 删除分类 | 管理员 |
| GET | /api/knowledge | 获取知识列表 | 否 |
| GET | /api/knowledge/{id} | 获取知识详情 | 否 |
| POST | /api/knowledge | 创建知识条目 | 教师 |
| PUT | /api/knowledge/{id} | 更新知识条目 | 教师 |
| DELETE | /api/knowledge/{id} | 删除知识条目 | 教师 |
| POST | /api/knowledge/import | 批量导入 | 教师 |

### 5.3 问答相关接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | /api/qa/ask | 提交问题 | 用户 |
| GET | /api/qa/history | 获取问答历史 | 用户 |
| GET | /api/qa/{id} | 获取问答详情 | 用户 |
| POST | /api/qa/{id}/feedback | 提交反馈 | 用户 |
| GET | /api/qa/similar | 获取相似问题 | 否 |
| POST | /api/qa/conversation | 创建会话 | 用户 |
| GET | /api/qa/conversations | 获取会话列表 | 用户 |

### 5.4 收藏相关接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | /api/favorites | 获取收藏列表 | 用户 |
| POST | /api/favorites | 添加收藏 | 用户 |
| DELETE | /api/favorites/{id} | 取消收藏 | 用户 |

### 5.5 统计相关接口

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | /api/stats/overview | 系统概览 | 管理员 |
| GET | /api/stats/user | 用户统计 | 管理员 |
| GET | /api/stats/qa | 问答统计 | 管理员 |

---

## 6. 前端页面设计

### 6.1 页面结构

```
├── 公共页面
│   ├── 首页 (/)
│   ├── 登录 (/login)
│   └── 注册 (/register)
│
├── 用户页面
│   ├── 个人中心 (/user)
│   ├── 问答历史 (/user/history)
│   ├── 我的收藏 (/user/favorites)
│   └── 设置 (/user/settings)
│
├── 知识库页面
│   ├── 知识库首页 (/knowledge)
│   ├── 分类详情 (/knowledge/category/:id)
│   └── 知识详情 (/knowledge/:id)
│
├── 问答页面
│   ├── 智能问答 (/qa)
│   ├── 会话详情 (/qa/conversation/:id)
│   └── 问答广场 (/qa/square)
│
└── 管理页面 (需管理员权限)
    ├── 用户管理 (/admin/users)
    ├── 知识管理 (/admin/knowledge)
    ├── 问答管理 (/admin/qa)
    └── 系统设置 (/admin/settings)
```

### 6.2 主要页面说明

#### 首页
- 系统介绍与功能展示
- 快速问答入口
- 热门知识推荐
- 系统统计信息

#### 智能问答页面
- 聊天式问答界面
- 消息气泡展示
- 知识来源折叠展示
- 追问建议列表
- 答案反馈按钮
- 历史会话切换

#### 知识库页面
- 分类导航树
- 知识卡片列表
- 搜索筛选功能
- 知识图谱可视化入口

#### 管理后台
- 数据仪表盘
- 用户CRUD操作
- 知识库管理
- 问答质量审核
- 系统配置

---

## 7. RAG引擎详细设计

### 7.1 向量检索流程

```
1. 文档预处理
   ├── 文本清洗（去除HTML、特殊字符）
   ├── 分句处理（按句子/段落分割）
   ├── 元数据提取（标题、分类、标签）
   └── 生成文档块（512-1024 tokens）

2. 向量化存储
   ├── 使用 text2vec-base-chinese 生成向量
   ├── 存储到 ChromaDB
   └── 保存元数据（id、来源、分类）

3. 检索过程
   ├── 问题向量化
   ├── Top-K 相似度检索（K=10）
   ├── 相似度阈值过滤（>0.5）
   └── 返回相关文档块
```

### 7.2 知识图谱构建

```
知识实体类型:
- 概念 (Concept): 网络安全术语、原理
- 技术 (Technique): 攻击技术、防御技术
- 工具 (Tool): 安全工具、软件
- 漏洞 (Vulnerability): 已知漏洞
- 事件 (Event): 安全事件

知识关系类型:
- is-a: 包含关系 (SQL注入 is-a Web安全)
- part-of: 组成关系 (XSS part-of Web安全)
- uses: 使用关系 (Nmap uses 网络扫描)
- caused-by: 因果关系 (DoS caused-by 流量攻击)
- related-to: 相关关系

图谱检索:
- 基于实体类型的邻居查询
- 基于关系类型的多跳查询
- 路径发现算法
```

### 7.3 结果融合算法 (RRF)

```python
def rrf_fusion(vector_results, graph_results, k=60):
    """
    Reciprocal Rank Fusion
    """
    scores = {}
    
    # 向量检索得分 (权重0.7)
    for rank, item in enumerate(vector_results):
        scores[item.id] = scores.get(item.id, 0) + 0.7 * (1 / (k + rank + 1))
    
    # 图谱检索得分 (权重0.3)
    for rank, item in enumerate(graph_results):
        scores[item.id] = scores.get(item.id, 0) + 0.3 * (1 / (k + rank + 1))
    
    # 排序返回
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 7.4 Prompt模板

```
系统提示词:
---
你是网络安全领域的专业教学助手"网安卫士"。
你的职责是:
1. 准确回答网络安全相关问题
2. 使用简洁易懂的语言解释复杂概念
3. 提供实际案例和代码示例
4. 标注答案的知识来源
5. 如不确定，明确告知用户

回答要求:
- 结构清晰，使用标题、列表等格式
- 复杂概念提供图示说明
- 包含相关的安全警告和最佳实践
- 引用可信的知识来源
---

用户问题:
{user_question}

相关上下文:
{context}

请基于以上上下文回答用户问题。如果上下文不足以回答，请基于你的网络安全知识回答，并明确说明这一点。
---
```

---

## 8. 项目目录结构

```
d:\workproject\work\work-5238\
├── backend/                      # 后端项目
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py             # 配置文件
│   │   ├── models/               # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── knowledge.py
│   │   │   └── qa.py
│   │   ├── routes/               # 路由
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── knowledge.py
│   │   │   ├── qa.py
│   │   │   └── admin.py
│   │   ├── services/             # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── rag_engine.py     # RAG核心引擎(兼容层)
│   │   │   ├── enhanced_rag_engine.py  # 增强版RAG引擎(含重排序)
│   │   │   ├── vector_store.py   # 向量存储(ChromaDB)
│   │   │   ├── secbert_embedding.py    # SecBERT向量化
│   │   │   ├── neo4j_graph.py   # Neo4j知识图谱
│   │   │   ├── graph_store.py   # 知识图谱(统一接口)
│   │   │   ├── document_parser.py     # 多格式文档解析
│   │   │   ├── text_chunker.py        # spaCy文本分块
│   │   │   └── data_processor.py      # 数据处理流水线
│   │   └── utils/                # 工具函数
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       └── database.py
│   ├── migrations/              # 数据库迁移
│   ├── requirements.txt
│   └── run.py                   # 入口文件
│
├── frontend/                     # 前端项目
│   ├── public/
│   ├── src/
│   │   ├── api/                 # API调用
│   │   ├── assets/              # 静态资源
│   │   ├── components/          # 公共组件
│   │   ├── router/              # 路由配置
│   │   ├── stores/              # Pinia状态
│   │   ├── utils/               # 工具函数
│   │   ├── views/               # 页面组件
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── docs/                         # 文档
│   ├── API文档.md
│   └── 部署指南.md
│
├── database/                     # 数据库脚本
│   └── init.sql
│
├── SPEC.md                       # 本文档
└── README.md                     # 项目说明
```

---

## 9. 部署方案

### 开发环境
- Python 3.10+
- Node.js 18+
- MySQL 8.0
- 8GB+ RAM (向量模型需要)

### 生产环境建议
- 使用Docker容器化部署
- Nginx反向代理
- HTTPS证书配置
- 数据库定期备份

---

## 10. 验收标准

### 功能验收
- [ ] 用户注册、登录、个人信息管理
- [ ] 知识库的CRUD操作
- [ ] 智能问答功能正常响应
- [ ] 多轮对话上下文保持
- [ ] 答案来源可追溯展示
- [ ] 收藏和历史记录功能

### 性能验收
- 问答响应时间 < 5秒
- 知识检索响应时间 < 1秒
- 支持100+并发用户

### 安全验收
- 用户密码加密存储
- JWT令牌认证
- API访问权限控制
- 输入内容过滤

---

## 11. 后续优化方向

1. **模型优化**: 引入专业知识微调的LLM
2. **知识图谱完善**: 自动构建知识点关联
3. **多模态**: 支持图片、图表解释
4. **离线部署**: 支持私有化部署
5. **智能出题**: 基于知识库自动生成习题
