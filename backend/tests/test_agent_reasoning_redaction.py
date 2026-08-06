# -*- coding: utf-8 -*-
"""A3 reasoning redaction and prompt safety tests (spec §3.3 / §A3.6)."""
from __future__ import annotations

from app import db
from app.models.agent_llm import LLMInvocation
from app.models.llm import LLMCallLog
from app.services.llm.contracts import LLMStreamChunk
from app.services.llm.redactor import redact_reasoning
from app.services.security_agent.event_service import EventService
from app.services.security_agent.llm_analysis import AgentLlmAnalysisService

from test_agent_llm_analysis import _FakeStreamProvider, _make_run


def test_redactor_masks_openai_style_keys():
    assert redact_reasoning("我的 key 是 sk-abcdefghijklmnopqrstuvw") == "我的 key 是 [REDACTED]"


def test_redactor_masks_bearer_tokens():
    result = redact_reasoning("调用时使用 Bearer abcdef1234567890abcdef")
    assert result == "调用时使用 [REDACTED]"


def test_redactor_masks_key_assignments():
    result = redact_reasoning("config: api_key=sk-abcdefghijklmnopqrstuvw")
    assert "sk-abcdefghijklmnopqrstuvw" not in result


def test_redactor_masks_private_key_blocks():
    block = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcw\n-----END PRIVATE KEY-----"
    result = redact_reasoning(f"包含私钥：{block}")
    assert "BEGIN PRIVATE KEY" not in result
    assert "[REDACTED]" in result


def test_redactor_drops_unsafe_delta():
    assert redact_reasoning("") is None
    assert redact_reasoning("sk-abcdefghijklmnopqrstuvw") == "[REDACTED]"
    assert redact_reasoning("   ") is None


def test_redactor_keeps_plain_reasoning():
    text = "先核对扫描证据，再判断是否存在越权风险。"
    assert redact_reasoning(text) == text


def test_analysis_stream_redacts_reasoning_before_emit(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        provider = _FakeStreamProvider(
            [
                LLMStreamChunk(reasoning_delta="包含密钥 sk-abcdefghijklmnopqrstuvw 的增量"),
                LLMStreamChunk(reasoning_delta="继续分析"),
                LLMStreamChunk(delta="结论：完成"),
                LLMStreamChunk(finished=True),
            ]
        )
        monkeypatch.setattr(
            "app.services.security_agent.llm_analysis.select_provider",
            lambda *args, **kwargs: provider,
        )

        AgentLlmAnalysisService(EventService()).analyze(run, trace_id="r1")

        deltas = [
            item.payload_json["delta"]
            for item in EventService().list_events(run.id)
            if item.event_type == "llm.reasoning_delta"
        ]
        joined = "".join(deltas)
        assert "sk-abcdefghijklmnopqrstuvw" not in joined
        assert "继续分析" in joined
        assert "[REDACTED]" in joined


def test_invocations_never_store_prompt_or_raw_output(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        raw = _FakeStreamProvider(
            [
                LLMStreamChunk(delta="分析结果文本"),
                LLMStreamChunk(finished=True, usage={"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12}),
            ]
        )
        from app.services.llm.call_logging import observe_provider

        observed = observe_provider(raw, user_id=run.created_by, operation="agent")
        monkeypatch.setattr(
            "app.services.security_agent.llm_analysis.select_provider",
            lambda *args, **kwargs: observed,
        )

        AgentLlmAnalysisService(EventService()).analyze(run, trace_id="r2")

        prompt = raw.requests[0].prompt
        invocation = LLMInvocation.query.filter_by(run_id=run.id).one()
        assert invocation.input_digest, "必须保存输入 digest"
        assert invocation.input_digest != prompt, "不得保存 prompt 原文"
        assert "确定性工具证据" not in repr(invocation.to_dict())
        assert "分析结果文本" not in repr(invocation.to_dict())
        log = LLMCallLog.query.filter_by(user_id=run.created_by).one()
        assert prompt not in repr(log.to_dict())
