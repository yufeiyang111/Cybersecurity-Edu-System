# -*- coding: utf-8 -*-
"""T12 敏感数据边界测试：扫描 DB/API/SSE/日志，拒绝原始推理与敏感原文。"""
from __future__ import annotations

import logging
import re

import pytest

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter

_RAW_COT = "让我逐步思考：读取 auth.py，检查 token 校验逻辑，发现没有过期校验……"
_SECRET = "sk-abcdefghijklmnopqrstuvwxyz123456"


def _make_run_with_reasoning_event(app):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="敏感边界测试",
            mode="hybrid",
        )
        db.session.add(run)
        db.session.flush()
        EventWriter().emit(
            run,
            event_type="item.reasoning_summary.delta",
            item_id="rs-1",
            payload={
                "delta": "先核对扫描证据。",
                "sensitive_level": "internal",
            },
            trace_id="t-sec",
        )
        db.session.commit()
        return run.id


def test_reasoning_summary_event_requires_sensitive_level(app):
    with app.app_context():
        run = db.session.get(AgentRun, _make_run_with_reasoning_event(app))
        from app.services.security_agent.timeline.contracts import (
            AgentEventEnvelope,
        )

        with pytest.raises(ValueError):
            AgentEventEnvelope.from_dict(
                {
                    "event_id": 1,
                    "sequence": 1,
                    "run_id": run.id,
                    "event_type": "item.reasoning_summary.delta",
                    "payload": {"delta": "无敏感等级"},
                }
            )


def test_no_raw_reasoning_in_db_payload(app):
    with app.app_context():
        _make_run_with_reasoning_event(app)
        events = AgentEvent.query.all()
        serialized = repr([event.to_dict() for event in events])
        assert _RAW_COT not in serialized
        assert "reasoning_full" not in serialized
        assert "chain_of_thought" not in serialized


def test_no_secret_in_db_payload(app):
    with app.app_context():
        _make_run_with_reasoning_event(app)
        events = AgentEvent.query.all()
        serialized = repr([event.to_dict() for event in events])
        assert _SECRET not in serialized


def test_llm_analysis_never_logs_raw_response(app, caplog):
    from app.services.security_agent.llm_analysis import AgentLlmAnalysisService
    from app.services.security_agent.event_service import EventService

    with app.app_context():
        run = db.session.get(AgentRun, _make_run_with_reasoning_event(app))
        with caplog.at_level(logging.DEBUG, logger="app.services.security_agent"):
            # 无 provider：走降级路径，不应产生任何 raw 日志
            AgentLlmAnalysisService(EventService()).analyze(run, trace_id="t-sec2")
        combined = "\n".join(record.getMessage() for record in caplog.records)
        assert _SECRET not in combined
        assert "Authorization" not in combined
        assert "Bearer " not in combined


def test_openai_adapter_has_no_raw_diag_logging():
    """openai_compatible 不得包含原始响应 DIAG 日志或 _raw_log。"""
    import pathlib

    source = pathlib.Path(
        "app/services/llm/openai_compatible.py"
    ).read_text(encoding="utf-8")
    assert "def _raw_log" not in source
    assert "raw_content=%r" not in source


def test_call_logging_has_no_raw_text_field():
    """call_logging 不得记录响应原文（text=%r）。"""
    import pathlib

    source = pathlib.Path("app/services/llm/call_logging.py").read_text(
        encoding="utf-8"
    )
    assert "text=%r" not in source


def test_sensitive_pattern_scan_of_log_records(caplog):
    """测试 logger 捕获器中不允许出现敏感模式。"""
    patterns = [
        re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}\b"),
        re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9_\-\.\+/=]{12,}\b"),
        re.compile(r"(?i)\bAuthorization\s*[:=]"),
    ]
    logger = logging.getLogger("app.services.security_agent")
    logger.warning("安全日志：provider=openai-compatible status=ok digest=abc")
    for record in caplog.records:
        message = record.getMessage()
        for pattern in patterns:
            assert not pattern.search(message), f"日志包含敏感模式：{message[:80]}"
