# -*- coding: utf-8 -*-
"""Agent LLM 分析测试：Provider 降级、流式解析、事件持久化、用量、调用日志、失败降级。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentArtifact,
    AgentMessage,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
)
from app.models.conversation import AgentConversation, AgentConversationMessage, AgentTurn
from app.models.llm import LLMCallLog
from app.models.security import ProjectSnapshot, SecurityProject, Workspace
from app.models.user import User
from app.services.llm.call_logging import observe_provider
from app.services.llm.contracts import LLMRequest, LLMStreamChunk
from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.checkpoint_service import CheckpointService
from app.services.security_agent.event_service import EventService
from app.services.security_agent.llm_analysis import (
    ANALYSIS_MESSAGE_TYPE,
    AgentLlmAnalysisService,
)
from app.services.security_agent.runner import InlinePlanRunner
from app.services.security_agent.state_machine import AgentStateMachine


class _FakeStreamProvider:
    """按测试用例给定的 chunk 序列流式产出的轻量 Provider。"""

    provider_name = "fake-agent"
    model = "fake-model"
    provider_config_id = None

    def __init__(self, chunks):
        self._chunks = chunks
        self.requests = []

    def generate_stream(self, request):
        self.requests.append(request)
        for chunk in self._chunks:
            yield chunk


class _BoomProvider:
    """调用即抛异常的 Provider，用于验证失败不吞异常且安全降级。"""

    provider_name = "boom-agent"
    model = None

    def generate_stream(self, request):
        raise RuntimeError("provider exploded")


def _make_run(
    *,
    status: str = AgentRunStatus.EXECUTING_TOOLS.value,
    with_turn: bool = False,
    with_evidence: bool = True,
):
    user = User(username="llm-agent", email="llm-agent@example.test", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="w", slug="w-llm")
    db.session.add(workspace)
    db.session.flush()
    project = SecurityProject(workspace_id=workspace.id, name="llm", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="c",
        storage_path="/tmp/nonexistent",
        file_count=2,
        total_bytes=100,
    )
    db.session.add(snapshot)
    db.session.flush()
    run = AgentRun(
        workspace_id=workspace.id,
        project_id=project.id,
        snapshot_id=snapshot.id,
        created_by=user.id,
        goal_text="检查项目后门风险",
        mode=AgentRunMode.BASELINE.value,
        status=status,
    )
    db.session.add(run)
    db.session.flush()

    if with_evidence:
        db.session.add(
            AgentArtifact(
                run_id=run.id,
                artifact_type="finding_set",
                summary="task #1: 3 findings",
                content_json={
                    "metrics": {
                        "task_id": 1,
                        "findings_count": 3,
                        "severity_counts": {"critical": 1, "high": 1, "low": 1},
                        "languages": ["python"],
                        "top_findings": [
                            {"rule_id": "sast-1", "severity": "high", "file_path": "app.py"}
                        ],
                    }
                },
            )
        )
        db.session.add(
            AgentArtifact(
                run_id=run.id,
                artifact_type="coverage_report",
                summary="task #1: 2 files",
                content_json={
                    "metrics": {
                        "total_files": 2,
                        "scanned_with_findings": 1,
                        "specialized_sast": 1,
                    }
                },
            )
        )

    if with_turn:
        conversation = AgentConversation(
            workspace_id=workspace.id,
            project_id=project.id,
            title="多轮会话",
            created_by=user.id,
            message_sequence=2,
            turn_sequence=1,
        )
        db.session.add(conversation)
        db.session.flush()
        message = AgentConversationMessage(
            conversation_id=conversation.id,
            client_message_id="msg-turn-0001",
            message_sequence=2,
            role="user",
            message_type="follow_up",
            content_redacted="第二轮输入：重点看后门",
            content_digest="d" * 64,
        )
        db.session.add(message)
        db.session.flush()
        turn = AgentTurn(
            conversation_id=conversation.id,
            turn_sequence=1,
            run_id=run.id,
            input_message_id=message.id,
        )
        db.session.add(turn)

    db.session.commit()
    return run


def _events(run_id: int) -> list[AgentEvent]:
    return EventService().list_events(run_id)


def _event_types(run_id: int) -> list[str]:
    return [item.event_type for item in _events(run_id)]


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "app.services.security_agent.llm_analysis.select_provider",
        lambda *args, **kwargs: provider,
    )


# ------------------------------------------------------------------ 无 Provider 降级


def test_no_provider_degrades_with_deterministic_summary(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        _patch_provider(monkeypatch, None)

        result = AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t1")

        assert result["degraded"] is True
        assert result["warning_code"] == "AGENT_PROVIDER_NOT_CONFIGURED"
        assert "LLM 分析暂不可用" in result["analysis"]
        assert "确定性工具证据摘要" in result["analysis"]
        assert "finding_set" in result["analysis"]
        assert result["provider"] is None

        types = _event_types(run.id)
        assert "llm.failed" in types
        assert "llm.completed" in types
        assert "warning.raised" in types
        assert "llm.started" not in types
        assert "llm.reasoning_delta" not in types

        warning = next(
            item for item in _events(run.id) if item.event_type == "warning.raised"
        )
        assert warning.payload_json["warning_codes"] == ["AGENT_PROVIDER_NOT_CONFIGURED"]
        failed = next(item for item in _events(run.id) if item.event_type == "llm.failed")
        assert failed.payload_json["agent_warning_code"] == "AGENT_PROVIDER_NOT_CONFIGURED"

        message = AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).one()
        assert message.role == "agent"
        assert "LLM 分析暂不可用" in message.content

        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.llm_call_count == 0, "未调用 Provider 不得累加调用次数"
        assert reloaded.total_tokens == 0


# ------------------------------------------------------------------ 正常流式


def test_stream_analysis_collects_reasoning_usage_and_persists_events(app, monkeypatch):
    with app.app_context():
        run = _make_run(with_turn=True)
        provider = _FakeStreamProvider(
            [
                LLMStreamChunk(reasoning_delta="先核对扫描证据"),
                LLMStreamChunk(delta="结论：存在后门风险。"),
                LLMStreamChunk(delta="建议加固入口鉴权。"),
                LLMStreamChunk(
                    finished=True,
                    usage={
                        "prompt_tokens": 30,
                        "completion_tokens": 12,
                        "total_tokens": 42,
                        "completion_tokens_details": {"reasoning_tokens": 5},
                    },
                ),
            ]
        )
        _patch_provider(monkeypatch, provider)

        result = AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t2")

        assert result["degraded"] is False
        assert result["analysis"] == "结论：存在后门风险。建议加固入口鉴权。"
        assert result["usage"]["tokens"] == 42
        assert result["usage"]["reasoning_tokens"] == 5
        assert result["provider"] == "fake-agent"

        request: LLMRequest = provider.requests[0]
        assert "第二轮输入：重点看后门" in request.prompt, "必须引用当前 Turn 的输入"
        assert "确定性工具证据" in request.prompt
        assert "finding_set" in request.prompt
        assert "checkpoint_service" not in request.prompt

        types = _event_types(run.id)
        assert "llm.started" in types
        assert "llm.completed" in types
        assert "llm.usage" in types
        assert "llm.failed" not in types
        assert "warning.raised" not in types

        deltas = [
            item.payload_json["delta"]
            for item in _events(run.id)
            if item.event_type == "llm.reasoning_delta"
        ]
        assert "".join(deltas) == "先核对扫描证据", "reasoning_delta 事件必须持久化且按序"

        usage_event = next(
            item for item in _events(run.id) if item.event_type == "llm.usage"
        )
        assert usage_event.payload_json["tokens"] == 42
        assert usage_event.payload_json["reasoning_tokens"] == 5

        completed = next(
            item for item in _events(run.id) if item.event_type == "llm.completed"
        )
        assert completed.payload_json["analysis"] == result["analysis"]

        message = AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).one()
        assert message.role == "agent"
        assert message.content == result["analysis"]

        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.llm_call_count == 1
        assert reloaded.input_tokens == 30
        assert reloaded.output_tokens == 12
        assert reloaded.reasoning_tokens == 5
        assert reloaded.total_tokens == 42


def test_agent_analysis_records_call_log(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        raw = _FakeStreamProvider(
            [
                LLMStreamChunk(delta="分析完成"),
                LLMStreamChunk(
                    finished=True,
                    usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                ),
            ]
        )
        observed = observe_provider(raw, user_id=run.created_by, operation="agent")
        _patch_provider(monkeypatch, observed)

        AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t3")

        log = LLMCallLog.query.filter_by(user_id=run.created_by).one()
        assert log.operation == "agent"
        assert log.status == "success"
        assert log.streaming is True
        assert log.total_tokens == 14
        assert log.input_tokens == 10
        assert log.output_tokens == 4
        assert "prompt" not in repr(log.to_dict())


# ------------------------------------------------------------------ 失败降级


def test_stream_exception_is_recorded_and_degrades_safely(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        _patch_provider(monkeypatch, _BoomProvider())

        result = AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t4")

        assert result["degraded"] is True
        assert result["warning_code"] == "AGENT_PROVIDER_UNHEALTHY"
        assert "LLM 分析暂不可用" in result["analysis"]

        types = _event_types(run.id)
        assert "llm.failed" in types
        assert "warning.raised" in types
        assert "llm.completed" in types
        assert "llm.reasoning_delta" not in types

        message = AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).one()
        assert message.role == "agent"
        assert "LLM 分析暂不可用" in message.content

        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded is not None, "失败不得导致 run 丢失"


def test_stream_warning_chunk_maps_to_agent_warning(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        provider = _FakeStreamProvider(
            [LLMStreamChunk(finished=True, warning_code="LLM_PROVIDER_TIMEOUT")]
        )
        _patch_provider(monkeypatch, provider)

        result = AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t5")

        assert result["degraded"] is True
        assert result["warning_code"] == "AGENT_PROVIDER_TIMEOUT"
        assert "超时" in result["analysis"]
        assert "llm.failed" in _event_types(run.id)


def test_empty_stream_degrades_as_invalid_response(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        provider = _FakeStreamProvider([LLMStreamChunk(finished=True)])
        _patch_provider(monkeypatch, provider)

        result = AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t6")

        assert result["degraded"] is True
        assert result["warning_code"] == "AGENT_PROVIDER_INVALID_RESPONSE"
        assert "llm.failed" in _event_types(run.id)


# ------------------------------------------------------------------ 幂等与停止


def test_analysis_is_idempotent(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        provider = _FakeStreamProvider(
            [LLMStreamChunk(delta="完成"), LLMStreamChunk(finished=True)]
        )
        _patch_provider(monkeypatch, provider)
        service = AgentLlmAnalysisService(EventService())

        first = service.analyze(run, trace_id="t7")
        second = service.analyze(run, trace_id="t7")

        assert first["degraded"] is False
        assert second is None
        assert AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).count() == 1
        assert len(provider.requests) == 1


def test_canceled_run_skips_analysis(app, monkeypatch):
    with app.app_context():
        run = _make_run(status=AgentRunStatus.CANCELED.value)
        provider = _FakeStreamProvider([])
        _patch_provider(monkeypatch, provider)

        result = AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t8")

        assert result is None
        assert provider.requests == []
        assert AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).count() == 0


# ------------------------------------------------------------------ runner 集成


def test_runner_invokes_analysis_and_transitions_to_evaluating_evidence(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        provider = _FakeStreamProvider(
            [
                LLMStreamChunk(reasoning_delta="推理中"),
                LLMStreamChunk(delta="分析结论"),
                LLMStreamChunk(finished=True),
            ]
        )
        _patch_provider(monkeypatch, provider)
        runner = InlinePlanRunner(
            state=AgentStateMachine(),
            events=EventService(),
            artifacts=ArtifactService(),
            checkpoints=CheckpointService(),
        )

        runner._run_llm_analysis(run.id, "t9")

        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.status.value == AgentRunStatus.EVALUATING_EVIDENCE.value
        assert AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).count() == 1

        runner._run_llm_analysis(run.id, "t9")
        assert AgentMessage.query.filter_by(
            run_id=run.id, message_type=ANALYSIS_MESSAGE_TYPE
        ).count() == 1, "恢复执行时不得重复分析"
