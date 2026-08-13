# -*- coding: utf-8 -*-
"""A-5/A-6 接线测试：会话压缩摘要生成与 Lease heartbeat 刷新。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_control import AgentConversationSummary
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunStatus,
)
from app.models.conversation import AgentConversation, AgentTurn
from app.services.security_agent.event_service import EventService
from app.services.security_agent.loop.engine import AgentLoopEngine
from app.services.security_agent.model.contracts import (
    AgentModelRequest,
    AgentModelResponse,
    ProviderCapabilities,
)
from app.services.security_agent.tools.registry import ToolRegistry


class _FinalOnlyProvider:
    """单轮模型：直接给最终回答（无工具调用）。"""

    provider_name = "final-only"
    model = "final-model"
    model_version = "1"
    provider_config_id = None

    def __init__(self) -> None:
        self.requests = []

    def agent_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_native_tools=True)

    def generate_agent(self, request: AgentModelRequest) -> AgentModelResponse:
        self.requests.append(request)
        return AgentModelResponse(
            content="审查完成：鉴权链路无越权风险。",
            tool_calls=(),
            finish_reason="stop",
            provider_name=self.provider_name,
            model=self.model,
        )


def _make_run_with_conversation() -> tuple[int, int]:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="重点检查鉴权与越权，确认所有接口都做了对象级授权校验",
        mode="hybrid",
        status=AgentRunStatus.EXECUTING_TOOLS.value,
    )
    db.session.add(run)
    db.session.flush()
    plan = AgentPlan(
        run_id=run.id,
        plan_version=1,
        planner_source="rule_based_policy",
        objective=run.goal_text,
    )
    db.session.add(plan)
    db.session.flush()
    for key, node_type in (
        ("inventory", AgentPlanNodeType.INVENTORY.value),
        ("baseline_scan", AgentPlanNodeType.BASELINE_SCAN.value),
        ("coverage_analysis", AgentPlanNodeType.COVERAGE_ANALYSIS.value),
        ("risk_ranking", AgentPlanNodeType.RISK_RANKING.value),
    ):
        db.session.add(
            AgentPlanNode(
                plan_id=plan.id,
                node_key=key,
                node_type=node_type,
                status=AgentPlanNodeStatus.SUCCEEDED.value,
                title=key,
                tool_name=key,
            )
        )
    conversation = AgentConversation(
        workspace_id=1,
        project_id=1,
        title="摘要接线测试",
        created_by=1,
    )
    db.session.add(conversation)
    db.session.flush()
    turn = AgentTurn(
        conversation_id=conversation.id,
        turn_sequence=1,
        run_id=run.id,
    )
    db.session.add(turn)
    db.session.commit()
    return run.id, conversation.id


def _registry() -> ToolRegistry:
    return ToolRegistry()


def test_truncated_context_generates_summary_with_watermark(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        app.config["AGENT_LOOP_MAX_CONTEXT_CHARS"] = 5
        app.config["AGENT_SUMMARY_MIN_NEW_SEQUENCES"] = 0
        run_id, conversation_id = _make_run_with_conversation()
        provider = _FinalOnlyProvider()
        result = AgentLoopEngine(
            provider=provider,
            registry=_registry(),
            events=EventService(),
        ).run_until_interrupt(run_id, "t-summary")
        run = db.session.get(AgentRun, run_id)
        assert result == "completed"

        summaries = AgentConversationSummary.query.filter_by(
            conversation_id=conversation_id
        ).order_by(AgentConversationSummary.summary_version.asc()).all()
        assert len(summaries) == 1, "超限必须生成结构化会话摘要"
        summary = summaries[0]
        assert summary.summary_version == 1
        assert summary.source_sequence_from <= summary.source_sequence_to
        assert summary.source_sequence_to <= run.last_event_sequence, (
            "摘要声明的水位区间不得超出实际事件水位"
        )
        assert len(summary.content_digest) == 64
        assert summary.summary_json.get("goal")
        assert summary.summary_json.get("budget") is not None
        assert "completed_actions_count" in summary.summary_json

        warning_types = [
            event.event_type
            for event in AgentEvent.query.filter_by(run_id=run_id).all()
        ]
        assert "warning.raised" in warning_types


def test_summary_not_regenerated_without_watermark_progress(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        app.config["AGENT_LOOP_MAX_CONTEXT_CHARS"] = 5
        app.config["AGENT_SUMMARY_MIN_NEW_SEQUENCES"] = 1000
        run_id, conversation_id = _make_run_with_conversation()
        run = db.session.get(AgentRun, run_id)
        engine = AgentLoopEngine(
            provider=_FinalOnlyProvider(),
            registry=_registry(),
            events=EventService(),
        )
        context = engine._assembler.build(
            run, conversation_id=conversation_id, max_context_chars=5
        )
        engine._compress_conversation(run, context, conversation_id, "t-1")
        engine._compress_conversation(run, context, conversation_id, "t-2")
        summaries = AgentConversationSummary.query.filter_by(
            conversation_id=conversation_id
        ).all()
        assert len(summaries) == 1, "水位前进不足时不得重复生成摘要版本"


def test_summary_failure_does_not_block_loop(app, monkeypatch):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        app.config["AGENT_LOOP_MAX_CONTEXT_CHARS"] = 5
        app.config["AGENT_SUMMARY_MIN_NEW_SEQUENCES"] = 0
        run_id, _ = _make_run_with_conversation()

        def _boom(self, *args, **kwargs):
            raise RuntimeError("summary storage down")

        from app.services.security_agent.loop.conversation_summary import (
            ConversationSummaryService,
        )

        monkeypatch.setattr(
            ConversationSummaryService, "create_summary", _boom
        )
        result = AgentLoopEngine(
            provider=_FinalOnlyProvider(),
            registry=_registry(),
            events=EventService(),
        ).run_until_interrupt(run_id, "t-summary-fail")
        assert result == "completed", "摘要失败只降级，不阻断 Agent 循环"
        run = db.session.get(AgentRun, run_id)
        assert "AGENT_CONTEXT_LIMITED" not in (run.warning_codes or [])


def test_engine_heartbeats_during_loop(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        run_id, _ = _make_run_with_conversation()
        AgentLoopEngine(
            provider=_FinalOnlyProvider(),
            registry=_registry(),
            events=EventService(),
        ).run_until_interrupt(run_id, "t-heartbeat")
        run = db.session.get(AgentRun, run_id)
        assert run.heartbeat_at is not None, "engine 每轮必须刷新 lease 心跳"


def test_executor_invokes_heartbeat_callback(app):
    from app.services.security_agent.tools.contracts import (
        ToolDescriptor,
        ToolResult,
    )
    from app.services.security_agent.tools.executor import ToolExecutor

    with app.app_context():
        run_id, _ = _make_run_with_conversation()
        run = db.session.get(AgentRun, run_id)
        plan = AgentPlan.query.filter_by(run_id=run_id).first()
        node = plan.nodes[0]
        from app.models.agent_runtime import AgentStepExecution

        step = AgentStepExecution(
            plan_node_id=node.id,
            run_id=run.id,
            attempt_number=1,
            worker_id="test",
            status="running",
        )
        db.session.add(step)
        db.session.flush()

        calls = []
        registry = ToolRegistry()
        registry.register(
            ToolDescriptor(
                name="hb_tool",
                version="1.0",
                category="test",
                description="心跳工具",
                input_schema={"type": "object", "properties": {}},
                risk_level="safe_read",
                timeout_seconds=5,
                idempotent=True,
            ),
            lambda ctx: ToolResult(status="succeeded", summary="ok"),
        )
        node.tool_name = "hb_tool"
        executor = ToolExecutor(
            registry,
            EventService(),
            heartbeat=lambda rid: calls.append(rid),
        )
        result = executor.execute(
            run, node, step, actor_id=1, trace_id="t-hb", input_payload={}
        )
        assert result.status == "succeeded"
        assert calls == [run.id], "工具 attempt 边界必须调用心跳回调"
