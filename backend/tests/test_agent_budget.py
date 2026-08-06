# -*- coding: utf-8 -*-
"""A3 budget tests: soft/hard limits block LLM work but never erase evidence."""
from __future__ import annotations

from datetime import datetime, timedelta

from app import db
from app.models.agent_llm import LLMInvocation
from app.services.security_agent.budget import budget_status
from app.services.security_agent.event_service import EventService
from app.services.security_agent.runner import InlinePlanRunner
from app.services.security_agent.state_machine import AgentStateMachine

from test_agent_llm_analysis import _make_run


def test_no_limits_means_no_soft_no_exhausted(app):
    with app.app_context():
        run = _make_run()
        status = budget_status(run)
        assert status["soft"] is False
        assert status["exhausted"] is False
        assert status["reached_codes"] == []


def test_soft_limit_at_80_percent(app):
    with app.app_context():
        run = _make_run()
        run.max_llm_calls = 10
        run.llm_call_count = 8
        db.session.commit()

        status = budget_status(run)
        assert status["soft"] is True
        assert status["exhausted"] is False
        assert status["reached_codes"] == ["AGENT_BUDGET_SOFT_LIMIT"]
        assert status["ratios"]["llm_calls"] == 0.8


def test_hard_limit_at_100_percent(app):
    with app.app_context():
        run = _make_run()
        run.max_llm_calls = 10
        run.llm_call_count = 10
        db.session.commit()

        status = budget_status(run)
        assert status["soft"] is True
        assert status["exhausted"] is True
        assert status["reached_codes"] == ["AGENT_BUDGET_EXHAUSTED"]


def test_wall_clock_budget_counts_from_started_at(app):
    with app.app_context():
        run = _make_run()
        run.max_wall_clock_seconds = 100
        run.started_at = datetime.utcnow() - timedelta(seconds=200)
        db.session.commit()

        status = budget_status(run)
        assert status["exhausted"] is True
        assert status["ratios"]["wall_clock_seconds"] >= 1.0


def test_run_parser_accepts_budget_and_rejects_invalid(app):
    from app.services.security_agent.service import _parse_budget

    values = _parse_budget(
        {
            "max_llm_calls": 5,
            "max_total_tokens": 1000,
            "max_estimated_cost": 0.5,
        }
    )
    assert values["max_llm_calls"] == 5
    assert values["max_estimated_cost"] == 0.5
    assert values == _parse_budget({}) if False else "max_tool_calls" not in values

    import pytest

    with pytest.raises(ValueError):
        _parse_budget({"max_llm_calls": 0})
    with pytest.raises(ValueError):
        _parse_budget({"max_estimated_cost": -1})
    with pytest.raises(ValueError):
        _parse_budget("not-a-dict")


def test_runner_skips_analysis_when_budget_exhausted(app, monkeypatch):
    with app.app_context():
        run = _make_run()
        run.max_llm_calls = 1
        run.llm_call_count = 1
        db.session.commit()

        runner = InlinePlanRunner(
            state=AgentStateMachine(),
            events=EventService(),
            artifacts=None,
            checkpoints=None,
        )
        runner._run_llm_analysis(run.id, "b1")

        assert LLMInvocation.query.filter_by(run_id=run.id).count() == 0
        types = [item.event_type for item in EventService().list_events(run.id)]
        assert "budget.updated" in types
        assert "warning.raised" in types
        warning = next(
            item for item in EventService().list_events(run.id) if item.event_type == "warning.raised"
        )
        assert "AGENT_BUDGET_EXHAUSTED" in warning.payload_json["warning_codes"]
