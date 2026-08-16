# -*- coding: utf-8 -*-
"""PlanEnvelope validation: structure, tool allowlist, mandatory baseline, DAG acyclicity."""
from __future__ import annotations

from app.models.agent_runtime import AgentPlanNodeType

# A2/A3/A4 阶段可用的节点类型（与已注册确定性工具一一对应）
AVAILABLE_NODE_TYPES = frozenset(
    {
        AgentPlanNodeType.INVENTORY.value,
        AgentPlanNodeType.BASELINE_SCAN.value,
        AgentPlanNodeType.COVERAGE_ANALYSIS.value,
        AgentPlanNodeType.RISK_RANKING.value,
        AgentPlanNodeType.REPORT_GENERATION.value,
        AgentPlanNodeType.REPOSITORY_MAPPING.value,
        AgentPlanNodeType.SEMANTIC_REVIEW.value,
    }
)

# 节点类型 -> 唯一允许的工具（防止类型与工具错配）
TOOL_BY_TYPE = {
    AgentPlanNodeType.INVENTORY.value: "inventory_snapshot",
    AgentPlanNodeType.BASELINE_SCAN.value: "run_baseline_scan",
    AgentPlanNodeType.COVERAGE_ANALYSIS.value: "get_scan_coverage",
    AgentPlanNodeType.RISK_RANKING.value: "rank_findings",
    AgentPlanNodeType.REPORT_GENERATION.value: "finalize_agent_report",
    AgentPlanNodeType.REPOSITORY_MAPPING.value: "map_repository",
    AgentPlanNodeType.SEMANTIC_REVIEW.value: "run_deep_review",
}

# repository_mapping 节点可选的图浏览/代码证据工具（A4），建图后用于按图取上下文
GRAPH_TOOLS = frozenset(
    {
        "get_route_map",
        "get_authentication_map",
        "search_code",
        "find_symbol_references",
        "get_related_files",
        "build_call_chain",
        "read_code_slice",
    }
)

# 强制性基线节点（确定性基线不可被 Planner 绕过，spec §3.2）
MANDATORY_NODE_TYPES = frozenset(
    {AgentPlanNodeType.INVENTORY.value, AgentPlanNodeType.BASELINE_SCAN.value}
)

DEEP_AUDIT_REQUIRED_NODES = {
    "inventory": AgentPlanNodeType.INVENTORY.value,
    "baseline_scan": AgentPlanNodeType.BASELINE_SCAN.value,
    "coverage_analysis": AgentPlanNodeType.COVERAGE_ANALYSIS.value,
    "risk_ranking": AgentPlanNodeType.RISK_RANKING.value,
    "deep_review": AgentPlanNodeType.SEMANTIC_REVIEW.value,
    "report": AgentPlanNodeType.REPORT_GENERATION.value,
}

DEFAULT_MAX_NODES = 8
DEFAULT_MAX_DEPTH = 6


class PlanValidationError(ValueError):
    """Raised when a plan envelope violates policy; the planner must not execute it."""


def validate_envelope(
    envelope: dict,
    *,
    available_tools: set[str] | frozenset[str],
    max_nodes: int = DEFAULT_MAX_NODES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    tool_allowed_modes: dict[str, set[str]] | None = None,
    run_mode: str | None = None,
) -> dict:
    """Validate a raw PlanEnvelope and return a normalized copy.

    Raises PlanValidationError with a reason; never returns a partially valid
    plan. Conditions DSL is not evaluated here (A5), only structure is checked.
    T06：可选 tool_allowed_modes + run_mode，模式禁止的工具被拒绝。
    """
    if not isinstance(envelope, dict):
        raise PlanValidationError("计划必须是 JSON 对象")

    objective = str(envelope.get("objective") or "").strip()
    if not objective:
        raise PlanValidationError("计划缺少 objective")

    nodes = envelope.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise PlanValidationError("计划必须包含至少一个节点")
    if len(nodes) > max_nodes:
        raise PlanValidationError(f"计划节点数超过上限 {max_nodes}")

    node_keys: set[str] = set()
    normalized_nodes: list[dict] = []
    node_types: set[str] = set()
    for index, raw_node in enumerate(nodes):
        node = _normalize_node(raw_node, index)
        if node["key"] in node_keys:
            raise PlanValidationError(f"节点 key 重复：{node['key']}")
        node_keys.add(node["key"])
        node_types.add(node["type"])
        normalized_nodes.append(node)

    missing_baseline = sorted(MANDATORY_NODE_TYPES - node_types)
    if missing_baseline:
        raise PlanValidationError(f"缺少强制基线节点：{', '.join(missing_baseline)}")

    edges = envelope.get("edges") or []
    if not isinstance(edges, list):
        raise PlanValidationError("edges 必须是数组")
    normalized_edges = [_normalize_edge(edge, node_keys, index) for index, edge in enumerate(edges)]
    _require_acyclic(normalized_edges, node_keys, max_depth=max_depth)
    if run_mode == "deep_audit":
        _require_deep_audit_contract(normalized_nodes, normalized_edges)

    completion_criteria = envelope.get("completion_criteria")
    if not isinstance(completion_criteria, list) or not completion_criteria:
        raise PlanValidationError("计划缺少 completion_criteria")

    for tool_name in (node.get("tool_name") for node in normalized_nodes):
        if tool_name is not None and tool_name not in available_tools:
            raise PlanValidationError(f"工具未注册或不允许：{tool_name}")
        if (
            tool_name is not None
            and run_mode is not None
            and tool_allowed_modes is not None
            and run_mode not in tool_allowed_modes.get(tool_name, set())
        ):
            raise PlanValidationError(
                f"运行模式 {run_mode} 禁止使用工具：{tool_name}"
            )

    return {
        "objective": objective[:4000],
        "hypotheses": _string_list(envelope.get("hypotheses") or [], "hypotheses", limit=8),
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "completion_criteria": _string_list(completion_criteria, "completion_criteria", limit=10),
        "decision_summary": str(envelope.get("decision_summary") or "")[:2000],
    }


def _require_deep_audit_contract(nodes: list[dict], edges: list[dict]) -> None:
    nodes_by_key = {node["key"]: node for node in nodes}
    invalid_keys = [
        key
        for key, expected_type in DEEP_AUDIT_REQUIRED_NODES.items()
        if nodes_by_key.get(key, {}).get("type") != expected_type
    ]
    if invalid_keys:
        raise PlanValidationError(
            "deep_audit 计划缺少或错误配置固定节点："
            + ", ".join(invalid_keys)
        )

    incoming = {
        key: {
            edge["from"]
            for edge in edges
            if edge["to"] == key
        }
        for key in DEEP_AUDIT_REQUIRED_NODES
    }
    missing_review_dependencies = {
        "coverage_analysis",
        "risk_ranking",
    } - incoming["deep_review"]
    if missing_review_dependencies:
        raise PlanValidationError(
            "deep_audit 的 deep_review 必须依赖："
            + ", ".join(sorted(missing_review_dependencies))
        )
    if "deep_review" not in incoming["report"]:
        raise PlanValidationError(
            "deep_audit 的 report 必须依赖 deep_review"
        )


def _normalize_node(raw_node: object, index: int) -> dict:
    if not isinstance(raw_node, dict):
        raise PlanValidationError(f"nodes[{index}] 必须是对象")
    key = str(raw_node.get("key") or "").strip()
    node_type = str(raw_node.get("type") or "").strip().lower()
    if not key:
        raise PlanValidationError(f"nodes[{index}] 缺少 key")
    if node_type not in AVAILABLE_NODE_TYPES:
        raise PlanValidationError(f"nodes[{index}] 类型不允许：{node_type or '空'}")
    title = str(raw_node.get("title") or "").strip()
    if not title:
        raise PlanValidationError(f"nodes[{index}] 缺少 title")
    tool_name = str(raw_node.get("tool_name") or "").strip() or None
    expected_tool = TOOL_BY_TYPE[node_type]
    if tool_name != expected_tool and not (
        node_type == AgentPlanNodeType.REPOSITORY_MAPPING.value and tool_name in GRAPH_TOOLS
    ):
        raise PlanValidationError(
            f"nodes[{index}] 工具与类型不匹配：{node_type} 只允许 {expected_tool}"
        )
    return {
        "key": key[:64],
        "type": node_type,
        "title": title[:500],
        "description": str(raw_node.get("description") or "")[:4000],
        "tool_name": tool_name,
    }


def _normalize_edge(raw_edge: object, node_keys: set[str], index: int) -> dict:
    if not isinstance(raw_edge, dict):
        raise PlanValidationError(f"edges[{index}] 必须是对象")
    source = str(raw_edge.get("from") or raw_edge.get("source") or "").strip()
    target = str(raw_edge.get("to") or raw_edge.get("target") or "").strip()
    if source not in node_keys or target not in node_keys:
        raise PlanValidationError(f"edges[{index}] 引用了不存在的节点")
    if source == target:
        raise PlanValidationError(f"edges[{index}] 不允许自环")
    edge_type = str(raw_edge.get("type") or "success").strip()
    if edge_type != "success":
        raise PlanValidationError(f"edges[{index}] 本阶段只支持 success 边")
    return {"from": source, "to": target, "type": edge_type}


def _require_acyclic(edges: list[dict], node_keys: set[str], *, max_depth: int) -> None:
    dependencies: dict[str, set[str]] = {key: set() for key in node_keys}
    for edge in edges:
        dependencies[edge["to"]].add(edge["from"])

    resolved: set[str] = set()
    pending = sorted(node_keys)
    depth = 0
    while pending:
        progress = False
        for key in list(pending):
            if dependencies[key] <= resolved:
                resolved.add(key)
                pending.remove(key)
                progress = True
        if not progress:
            cycle = sorted(pending)
            raise PlanValidationError(f"计划存在环或依赖缺失：{', '.join(cycle[:5])}")
        depth += 1
        if depth > max_depth:
            raise PlanValidationError(f"计划深度超过上限 {max_depth}")


def _string_list(value: object, field: str, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        raise PlanValidationError(f"{field} 必须是数组")
    items = [str(item).strip()[:500] for item in value if str(item).strip()]
    if len(items) > limit:
        raise PlanValidationError(f"{field} 数量超过上限 {limit}")
    return items
