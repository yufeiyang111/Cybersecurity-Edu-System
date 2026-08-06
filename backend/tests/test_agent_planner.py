# -*- coding: utf-8 -*-
"""A3 planner tests: LLM-generated PlanEnvelope with honest rule-based fallback."""
from __future__ import annotations

import json

from app import db
from app.models.agent_runtime import AgentPlan, AgentPlanNodeStatus
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


class _PlannerProvider:
    provider_name = "planner-fake"
    model = "fake-model"
    model_version = None
    provider_config_id = None

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

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
