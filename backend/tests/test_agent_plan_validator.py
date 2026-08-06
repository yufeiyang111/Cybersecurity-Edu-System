# -*- coding: utf-8 -*-
"""PlanEnvelope validator tests: baseline mandate, tool allowlist, DAG acyclicity."""
from __future__ import annotations

import pytest

from app.services.security_agent.plan_validator import PlanValidationError, validate_envelope

AVAILABLE_TOOLS = {
    "inventory_snapshot",
    "run_baseline_scan",
    "get_scan_coverage",
    "rank_findings",
    "finalize_agent_report",
}

_LEGAL_NODES = [
    {"key": "inventory", "type": "inventory", "title": "t", "tool_name": "inventory_snapshot"},
    {"key": "scan", "type": "baseline_scan", "title": "t", "tool_name": "run_baseline_scan"},
    {"key": "coverage", "type": "coverage_analysis", "title": "t", "tool_name": "get_scan_coverage"},
    {"key": "risk", "type": "risk_ranking", "title": "t", "tool_name": "rank_findings"},
    {"key": "report", "type": "report_generation", "title": "t", "tool_name": "finalize_agent_report"},
]

_LEGAL_EDGES = [
    {"from": "inventory", "to": "scan", "type": "success"},
    {"from": "scan", "to": "coverage", "type": "success"},
    {"from": "scan", "to": "risk", "type": "success"},
    {"from": "coverage", "to": "report", "type": "success"},
    {"from": "risk", "to": "report", "type": "success"},
]


def _envelope(**overrides):
    envelope = {
        "objective": "检查风险",
        "nodes": _LEGAL_NODES,
        "edges": _LEGAL_EDGES,
        "completion_criteria": ["完成"],
        "decision_summary": "原因",
    }
    envelope.update(overrides)
    return envelope


def test_valid_envelope_passes():
    result = validate_envelope(_envelope(), available_tools=AVAILABLE_TOOLS)
    assert result["objective"] == "检查风险"
    assert len(result["nodes"]) == 5


def test_missing_mandatory_baseline_node_rejected():
    nodes = [node for node in _LEGAL_NODES if node["key"] != "inventory"]
    with pytest.raises(PlanValidationError, match="强制基线节点"):
        validate_envelope(_envelope(nodes=nodes), available_tools=AVAILABLE_TOOLS)


def test_unregistered_tool_rejected():
    nodes = list(_LEGAL_NODES)
    nodes[1] = {**nodes[1], "tool_name": "run_evil_command"}
    with pytest.raises(PlanValidationError, match="工具与类型不匹配|未注册"):
        validate_envelope(_envelope(nodes=nodes), available_tools=AVAILABLE_TOOLS)


def test_tool_type_mismatch_rejected():
    nodes = list(_LEGAL_NODES)
    nodes[0] = {**nodes[0], "tool_name": "run_baseline_scan"}
    with pytest.raises(PlanValidationError, match="工具与类型不匹配"):
        validate_envelope(_envelope(nodes=nodes), available_tools=AVAILABLE_TOOLS)


def test_cycle_rejected():
    edges = [
        {"from": "inventory", "to": "scan", "type": "success"},
        {"from": "scan", "to": "inventory", "type": "success"},
    ]
    with pytest.raises(PlanValidationError, match="环|依赖缺失"):
        validate_envelope(_envelope(edges=edges), available_tools=AVAILABLE_TOOLS)


def test_self_loop_rejected():
    edges = [{"from": "inventory", "to": "inventory", "type": "success"}]
    with pytest.raises(PlanValidationError, match="自环"):
        validate_envelope(_envelope(edges=edges), available_tools=AVAILABLE_TOOLS)


def test_edge_referencing_missing_node_rejected():
    edges = [{"from": "ghost", "to": "scan", "type": "success"}]
    with pytest.raises(PlanValidationError, match="不存在的节点"):
        validate_envelope(_envelope(edges=edges), available_tools=AVAILABLE_TOOLS)


def test_too_many_nodes_rejected():
    nodes = list(_LEGAL_NODES) + [
        {"key": f"extra-{index}", "type": "coverage_analysis", "title": "t", "tool_name": "get_scan_coverage"}
        for index in range(10)
    ]
    with pytest.raises(PlanValidationError, match="上限"):
        validate_envelope(_envelope(nodes=nodes), available_tools=AVAILABLE_TOOLS, max_nodes=8)


def test_duplicate_node_key_rejected():
    nodes = list(_LEGAL_NODES)
    nodes.append({**nodes[0]})
    with pytest.raises(PlanValidationError, match="重复"):
        validate_envelope(_envelope(nodes=nodes), available_tools=AVAILABLE_TOOLS)


def test_missing_completion_criteria_rejected():
    with pytest.raises(PlanValidationError, match="completion_criteria"):
        validate_envelope(_envelope(completion_criteria=[]), available_tools=AVAILABLE_TOOLS)


def test_non_success_edge_rejected():
    edges = [{"from": "inventory", "to": "scan", "type": "evidence_gap"}]
    with pytest.raises(PlanValidationError, match="success"):
        validate_envelope(_envelope(edges=edges), available_tools=AVAILABLE_TOOLS)
