# -*- coding: utf-8 -*-
"""A3 planner tests: LLM-generated PlanEnvelope with honest rule-based fallback."""
from __future__ import annotations

import json

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRunMode,
)
from app.services.llm.contracts import LLMResponse
from app.services.security_agent.event_service import EventService
from app.services.security_agent.planner import PlanPlanner

from test_agent_llm_analysis import _make_run

VALID_ENVELOPE = {
    "objective": "检查项目后门风险",
    "hypotheses": ["可能存在硬编码后门"],
    "nodes": [
        {"key": "inventory", "type": "inventory", "title": "清点快照文件", "description": "清点", "tool_name": "inventory_snapshot"},
        {"key": "baseline_scan", "type": "baseline_scan", "title": "执行基线扫描", "description": "扫描", "tool_name": "run_baseline_scan"},
        {"key": "coverage", "type": "coverage_analysis", "title": "分析覆盖", "description": "覆盖", "tool_name": "get_scan_coverage"},
        {"key": "risk", "type": "risk_ranking", "title": "风险排序", "description": "排序", "tool_name": "rank_findings"},
        {"key": "report", "type": "report_generation", "title": "生成摘要", "description": "报告", "tool_name": "finalize_agent_report"},
    ],
    "edges": [
        {"from": "inventory", "to": "baseline_scan", "type": "success"},
        {"from": "baseline_scan", "to": "coverage", "type": "success"},
        {"from": "baseline_scan", "to": "risk", "type": "success"},
        {"from": "coverage", "to": "report", "type": "success"},
        {"from": "risk", "to": "report", "type": "success"},
    ],
    "completion_criteria": ["全部节点完成"],
    "decision_summary": "先基线扫描再分析覆盖与风险",
}


VALID_DEEP_ENVELOPE = {
    "objective": "检查项目高风险攻击路径",
    "hypotheses": ["高风险发现可能存在可利用调用路径"],
    "nodes": [
        {
            "key": "inventory",
            "type": "inventory",
            "title": "清点快照文件",
            "description": "清点",
            "tool_name": "inventory_snapshot",
        },
        {
            "key": "baseline_scan",
            "type": "baseline_scan",
            "title": "执行基线扫描",
            "description": "扫描",
            "tool_name": "run_baseline_scan",
        },
        {
            "key": "coverage_analysis",
            "type": "coverage_analysis",
            "title": "分析覆盖",
            "description": "覆盖",
            "tool_name": "get_scan_coverage",
        },
        {
            "key": "risk_ranking",
            "type": "risk_ranking",
            "title": "风险排序",
            "description": "排序",
            "tool_name": "rank_findings",
        },
        {
            "key": "deep_review",
            "type": "semantic_review",
            "title": "执行深度证据审查",
            "description": "核查高风险发现的代码位置、调用路径、可利用性与证据缺口。",
            "tool_name": "run_deep_review",
        },
        {
            "key": "report",
            "type": "report_generation",
            "title": "生成摘要",
            "description": "报告",
            "tool_name": "finalize_agent_report",
        },
    ],
    "edges": [
        {"from": "inventory", "to": "baseline_scan", "type": "success"},
        {"from": "baseline_scan", "to": "coverage_analysis", "type": "success"},
        {"from": "baseline_scan", "to": "risk_ranking", "type": "success"},
        {"from": "coverage_analysis", "to": "deep_review", "type": "success"},
        {"from": "risk_ranking", "to": "deep_review", "type": "success"},
        {"from": "coverage_analysis", "to": "report", "type": "success"},
        {"from": "risk_ranking", "to": "report", "type": "success"},
        {"from": "deep_review", "to": "report", "type": "success"},
    ],
    "completion_criteria": ["基线节点完成", "deep_review 完成", "报告完成"],
    "decision_summary": "先执行基线扫描，再完成深度证据审查与运行摘要。",
}

class _PlannerProvider:
    provider_name = "planner-fake"
    model = "fake-model"
    model_version = None
    provider_config_id = None

    def __init__(self, responses, max_tokens=None):
        self._responses = list(responses)
        self.requests = []
        self.max_tokens = max_tokens

    def generate(self, request):
        self.requests.append(request)
        return self._responses.pop(0)


def _ok_response(text):
    return LLMResponse(
        text=text,
        provider_name="planner-fake",
        model="fake-model",
        status_code=200,
        usage={"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50},
    )


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "app.services.security_agent.planner.select_provider",
        lambda *args, **kwargs: provider,
    )


def _plan_events(run_id):
    return EventService().list_events(run_id)


def test_no_provider_falls_back_to_rule_plan_with_reason(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        _patch_provider(monkeypatch, None)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p1")

        assert plan.planner_source == "rule_based_policy"
        assert run.planner_source == "rule_based_policy"
        assert len(plan.nodes) == 5
        assert plan.nodes[0].status == AgentPlanNodeStatus.READY.value

        created = next(
            item for item in _plan_events(run.id) if item.event_type == "plan.created"
        )
        assert created.payload_json["planner_source"] == "rule_based_policy"
        assert "未配置 LLM Provider" in created.payload_json["fallback_reason"]
        assert "llm_live" not in created.payload_json["planner_source"]




def test_deep_audit_fallback_plan_contains_required_deep_review(app, monkeypatch):
    """无 Provider 时 Deep Audit 也必须落下真实可执行的深度审查节点。"""
    with app.app_context():
        run = _make_run()
        run.mode = AgentRunMode.DEEP_AUDIT.value
        db.session.commit()
        _patch_provider(monkeypatch, None)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p-deep-fallback")

        nodes = {node.node_key: node for node in plan.nodes}
        assert plan.planner_source == "rule_based_policy"
        assert len(nodes) == 6
        assert nodes["deep_review"].node_type == AgentPlanNodeType.SEMANTIC_REVIEW.value
        assert nodes["deep_review"].tool_name == "run_deep_review"
        assert nodes["deep_review"].depends_on_json == [
            "coverage_analysis",
            "risk_ranking",
        ]
        assert nodes["deep_review"].input_json["focus"]
        assert "deep_review" in nodes["report"].depends_on_json
        assert any("deep_review" in item for item in plan.completion_criteria_json)
        assert "深度证据审查" in plan.decision_summary


def test_deep_audit_llm_plan_missing_deep_review_falls_back(app, monkeypatch):
    """LLM 漏掉深度审查时必须修复一次，仍不合格则回退安全策略计划。"""
    with app.app_context():
        run = _make_run()
        run.mode = AgentRunMode.DEEP_AUDIT.value
        db.session.commit()
        provider = _PlannerProvider(
            [
                _ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False)),
                _ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False)),
            ]
        )
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p-deep-repair")

        assert plan.planner_source == "rule_based_policy"
        assert len(provider.requests) == 2
        assert "deep_review" in provider.requests[0].prompt
        assert any(node.node_key == "deep_review" for node in plan.nodes)


def test_deep_audit_llm_plan_persists_safe_default_review_focus(app, monkeypatch):
    """LLM 只声明审查节点，服务端仍负责补入安全、可复现的审查焦点。"""
    with app.app_context():
        run = _make_run()
        run.mode = AgentRunMode.DEEP_AUDIT.value
        db.session.commit()
        provider = _PlannerProvider(
            [_ok_response(json.dumps(VALID_DEEP_ENVELOPE, ensure_ascii=False))]
        )
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p-deep-llm")

        deep_review = next(node for node in plan.nodes if node.node_key == "deep_review")
        assert plan.planner_source == "llm_live"
        assert deep_review.node_type == AgentPlanNodeType.SEMANTIC_REVIEW.value
        assert deep_review.tool_name == "run_deep_review"
        assert deep_review.input_json["focus"]
        assert "高危" in deep_review.input_json["focus"]


def test_valid_envelope_persists_llm_plan(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        provider = _PlannerProvider(
            [_ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False))]
        )
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p2")

        assert plan.planner_source == "llm_live"
        assert plan.objective == "检查项目后门风险"
        assert plan.hypotheses_json == ["可能存在硬编码后门"]
        keys = [node.node_key for node in plan.nodes]
        assert keys == ["inventory", "baseline_scan", "coverage", "risk", "report"]
        assert len(plan.edges) == 5

        created = next(
            item for item in _plan_events(run.id) if item.event_type == "plan.created"
        )
        assert created.payload_json["planner_source"] == "llm_live"
        assert "fallback_reason" not in created.payload_json

        prompt = provider.requests[0].prompt
        assert "检查项目后门风险" in prompt
        assert "inventory_snapshot" in prompt, "工具清单必须进入规划提示"


def test_invalid_envelope_twice_falls_back_after_repair(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        bad_envelope = {
            "objective": "x",
            "nodes": [
                {"key": "inventory", "type": "inventory", "title": "t", "tool_name": "inventory_snapshot"}
            ],
            "edges": [],
            "completion_criteria": ["c"],
        }
        provider = _PlannerProvider(
            [
                _ok_response(json.dumps(bad_envelope)),
                _ok_response(json.dumps(bad_envelope)),
            ]
        )
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p3")

        assert plan.planner_source == "rule_based_policy"
        assert len(provider.requests) == 2, "必须尝试 Plan Repair 一次"
        assert "失败原因" in provider.requests[1].prompt

        types = [item.event_type for item in _plan_events(run.id)]
        assert "warning.raised" in types
        warning = next(
            item
            for item in _plan_events(run.id)
            if item.event_type == "warning.raised"
        )
        assert "AGENT_PLAN_REPAIR_EXHAUSTED" in warning.payload_json["warning_codes"]


def test_repair_succeeds_on_second_attempt(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        broken = dict(VALID_ENVELOPE)
        broken["edges"] = [{"from": "nope", "to": "inventory", "type": "success"}]
        provider = _PlannerProvider(
            [
                _ok_response(json.dumps(broken, ensure_ascii=False)),
                _ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False)),
            ]
        )
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p4")

        assert plan.planner_source == "llm_live"
        assert len(provider.requests) == 2


def test_planner_uses_user_configured_max_tokens(app, monkeypatch):
    """用户 Provider 配置了 max_tokens 时，Planner 请求必须使用用户配置值。"""
    with app.app_context():
        run = _make_run()
        provider = _PlannerProvider(
            [_ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False))],
            max_tokens=8192,
        )
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p6")

        assert plan.planner_source == "llm_live"
        assert provider.requests[0].max_tokens == 8192


def test_planner_falls_back_to_default_max_tokens(app, monkeypatch):
    """用户未配置 max_tokens 时，Planner 使用代码默认值 1500。"""
    with app.app_context():
        run = _make_run()
        provider = _PlannerProvider(
            [_ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False))],
            max_tokens=None,
        )
        _patch_provider(monkeypatch, provider)

        PlanPlanner(EventService()).generate_plan(run, trace_id="p7")

        assert provider.requests[0].max_tokens == 1500


def test_budget_exhausted_blocks_llm_planning(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        run.max_llm_calls = 1
        run.llm_call_count = 1
        db.session.commit()
        provider = _PlannerProvider([])
        _patch_provider(monkeypatch, provider)

        plan = PlanPlanner(EventService()).generate_plan(run, trace_id="p5")

        assert plan.planner_source == "rule_based_policy"
        assert provider.requests == [], "预算耗尽时不得调用 LLM"
        types = [item.event_type for item in _plan_events(run.id)]
        assert "budget.updated" in types
        assert "warning.raised" in types


def test_parse_envelope_unwraps_wrapper_keys():
    from app.services.security_agent.prompt_templates.planner_v1 import parse_plan_envelope

    wrapped = json.dumps({"plan_envelope": VALID_ENVELOPE}, ensure_ascii=False)
    parsed = parse_plan_envelope(f"```json\n{wrapped}\n```")
    assert parsed["objective"] == "检查项目后门风险"
    assert parse_plan_envelope(json.dumps({"data": VALID_ENVELOPE}))["objective"] == "检查项目后门风险"


def test_runner_build_plan_delegates_to_llm_planner(app, monkeypatch):
    from app.services.security_agent.artifact_service import ArtifactService
    from app.services.security_agent.checkpoint_service import CheckpointService
    from app.services.security_agent.runner import InlinePlanRunner
    from app.services.security_agent.state_machine import AgentStateMachine

    with app.app_context():
        run = _make_run()
        provider = _PlannerProvider(
            [_ok_response(json.dumps(VALID_ENVELOPE, ensure_ascii=False))]
        )
        _patch_provider(monkeypatch, provider)
        runner = InlinePlanRunner(
            state=AgentStateMachine(),
            events=EventService(),
            artifacts=ArtifactService(),
            checkpoints=CheckpointService(),
        )

        plan = runner._build_plan(run, "p6")

        assert plan.planner_source == "llm_live"
        assert run.planner_source == "llm_live"
        assert run.plan_version == 1
        from app.models.agent_llm import LLMInvocation

        invocation = LLMInvocation.query.filter_by(run_id=run.id).one()
        assert invocation.operation == "planner"
        assert invocation.status == "success"


def test_plan_created_emits_v2_item_event_when_flag_on(app, monkeypatch):
    """Event v2 开启时计划事件必须是 item.plan.created 且带 item_id。"""
    from app.models.agent_events import AgentEvent

    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        run = _make_run()
        _patch_provider(monkeypatch, None)

        PlanPlanner(EventService()).generate_plan(run, trace_id="p-v2")

        created = (
            AgentEvent.query.filter_by(run_id=run.id, event_type="item.plan.created")
            .one()
        )
        assert created.schema_version == 2
        assert created.item_public_id == "plan_v1"
        assert created.payload_json["planner_source"] == "rule_based_policy"
