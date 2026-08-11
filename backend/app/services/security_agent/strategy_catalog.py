# -*- coding: utf-8 -*-
"""路线目录（Strategy Catalog）：证据 → 决策的声明式映射（A5）。

每条路线 = 触发条件（evidence 指标）+ 动作（新增计划节点 NodeSpec）+ reason_code。
- evaluate_evidence：自动重规划判定（高风险 finding → 相关文件分析）。
- user_direction_nodes：用户追加方向 → 节点集（按关键词匹配，无命中走默认图分析）。
- 限制参数（max_replans / max_plan_nodes / max_same_failure_route）由 replanner 执行。
本模块不落库、不改状态，只做纯函数判定。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.agent_runtime import AgentPlanNodeType

# ---------------------------------------------------------------- reason codes

REASON_HIGH_FINDINGS = "high_findings_require_related_review"
REASON_USER_DIRECTION = "user_direction_extends_plan"
REASON_FAILED_ROUTE = "failed_route_switched"

# 自动 replan 已添加的节点 key 前缀（防止同计划重复追加）
_RELATED_NODE_PREFIX = "related_"
_DIRECTION_NODE_PREFIX = "direction_"

# 用户方向关键词 → （方向名, 工具节点）
_DIRECTION_RULES: list[tuple[tuple[str, ...], str, str, dict]] = [
    (
        ("auth", "鉴权", "认证", "登录", "权限", "越权", "admin"),
        "auth",
        "get_authentication_map",
        {},
    ),
    (
        ("upload", "上传", "文件上传", "multipart"),
        "upload",
        "search_code",
        {"query": "upload"},
    ),
    (
        ("sql", "数据库", "查询", "注入", "mysql", "postgres"),
        "sql",
        "search_code",
        {"query": "execute"},
    ),
    (
        ("session", "会话", "cookie", "token", "jwt"),
        "session",
        "search_code",
        {"query": "session"},
    ),
]


@dataclass(frozen=True)
class NodeSpec:
    """计划新节点的声明式描述；由 replanner 落库为 AgentPlanNode。"""

    key: str
    node_type: str
    title: str
    description: str
    tool_name: str
    depends_on: tuple[str, ...] = ()
    input: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    """策略判定结果：是否重规划 + 原因 + 新增节点。"""

    should_replan: bool = False
    reason_code: str | None = None
    decision_type: str = "auto"
    node_specs: tuple[NodeSpec, ...] = ()
    decision_summary: str = ""


def _graph_node(key: str) -> NodeSpec:
    """建图前置节点：幂等、可缓存，保证后续图工具可用。"""
    return NodeSpec(
        key=key,
        node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
        title="构建项目安全图",
        description="为快照构建项目安全有向图（幂等，命中缓存时秒回）。",
        tool_name="map_repository",
    )


def related_review_nodes(high_files: tuple[str, ...]) -> list[NodeSpec]:
    """高风险 finding 的相关文件分析 + Deep Review 节点（自动重规划路线）。"""
    specs: list[NodeSpec] = [_graph_node("related_graph_build")]
    if high_files:
        specs.append(
            NodeSpec(
                key="related_high_finding_files",
                node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
                title="高风险 finding 相关文件分析",
                description=f"分析高危发现文件 {high_files[0]} 的关联节点与调用链。",
                tool_name="get_related_files",
                depends_on=("related_graph_build",),
                input={"file_path": high_files[0], "limit": 20, "offset": 0},
            )
        )
        specs.append(
            NodeSpec(
                key="related_deep_review",
                node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
                title="高风险 finding 深度审查",
                description=(
                    "对高风险发现文件执行 Deep Review：读取受限代码切片、"
                    "检索 RAG 知识引用，生成带证据链的 Observation 结论。"
                ),
                tool_name="run_deep_review",
                depends_on=("related_high_finding_files",),
                input={"focus": f"深度审查 {high_files[0]} 中的高风险安全发现", "file_hints": [high_files[0]]},
            )
        )
    specs.append(
        NodeSpec(
            key="related_route_overview",
            node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
            title="路由/入口概览",
            description="读取项目路由与入口节点，评估攻击面暴露情况。",
            tool_name="get_route_map",
            depends_on=("related_graph_build",),
            input={"limit": 50, "offset": 0},
        )
    )
    return specs


def user_direction_nodes(direction: str) -> list[NodeSpec]:
    """用户追加方向 → 计划节点集（关键词匹配，无命中走默认路由概览）。"""
    normalized = (direction or "").strip()
    tool_name = "get_route_map"
    input_payload: dict = {"limit": 50, "offset": 0}
    focus = "路由与入口"
    for keywords, label, candidate_tool, candidate_input in _DIRECTION_RULES:
        if any(keyword in normalized.lower() for keyword in keywords):
            tool_name = candidate_tool
            input_payload = dict(candidate_input)
            focus = label
            break
    return [
        _graph_node("direction_graph_build"),
        NodeSpec(
            key="direction_focused_review",
            node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
            title=f"定向分析：{focus}",
            description=f"根据用户追加方向「{direction[:100]}」执行定向分析。",
            tool_name=tool_name,
            depends_on=("direction_graph_build",),
            input=input_payload,
        ),
    ]


def evaluate_evidence(evidence, existing_node_keys: set[str]) -> StrategyDecision:
    """自动重规划判定：高风险 finding 且当前计划未覆盖相关文件分析时触发。"""
    if evidence.high_severity_count <= 0:
        return StrategyDecision()
    if any(key.startswith(_RELATED_NODE_PREFIX) for key in existing_node_keys):
        return StrategyDecision()
    specs = tuple(related_review_nodes(evidence.high_finding_files))
    if not specs:
        return StrategyDecision()
    return StrategyDecision(
        should_replan=True,
        reason_code=REASON_HIGH_FINDINGS,
        decision_type="auto",
        node_specs=specs,
        decision_summary=(
            f"基线扫描发现 {evidence.high_severity_count} 个高危/严重 finding，"
            "追加相关文件分析与路由概览节点以评估风险面。"
        ),
    )


def normalize_user_direction_nodes(direction: str) -> tuple[NodeSpec, ...]:
    """用户方向节点集的规范化入口（供 replanner 与 API 复用）。"""
    return tuple(user_direction_nodes(direction))
