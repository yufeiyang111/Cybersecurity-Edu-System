# -*- coding: utf-8 -*-
"""A3 invocation & cost tests: per-run LLM invocation audit and honest costs."""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_llm import LLMInvocation, LLMPriceCatalog
from app.models.agent_runtime import AgentRun
from app.services.security_agent.cost_service import run_costs
from app.services.security_agent.llm_invocation import (
    USAGE_SOURCE_ESTIMATED,
    USAGE_SOURCE_PROVIDER_REPORTED,
    USAGE_SOURCE_UNKNOWN,
    record_invocation,
)

from test_agent_llm_analysis import _make_run


class _Provider:
    provider_name = "deepseek-chat"
    model = "deepseek-chat"
    model_version = None
    provider_config_id = 7


def _priced_run(app):
    run = _make_run()
    db.session.add(
        LLMPriceCatalog(
            provider_name="deepseek-chat",
            model="deepseek-chat",
            currency="USD",
            input_price_per_million=0.27,
            cached_input_price_per_million=0.027,
            output_price_per_million=1.1,
            reasoning_price_per_million=0,
            pricing_version="builtin-v1",
        )
    )
    db.session.commit()
    return run


def test_invocation_records_usage_cost_and_accumulates_run(app):
    with app.app_context():
        run = _priced_run(app)

        record_invocation(
            run,
            provider=_Provider(),
            operation="planner",
            status="success",
            input_tokens=1000,
            output_tokens=500,
            cached_input_tokens=200,
            reasoning_tokens=50,
            total_tokens=1700,
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED,
            input_digest="a" * 64,
            prompt_template_version="planner-v1",
        )
        db.session.commit()

        invocation = LLMInvocation.query.filter_by(run_id=run.id).one()
        assert invocation.operation == "planner"
        assert invocation.usage_source == "provider_reported"
        assert invocation.pricing_version == "builtin-v1"
        assert invocation.total_tokens == 1700
        # 1000*0.27/1e6 + 200*0.027/1e6 + 500*1.1/1e6 = 0.00027 + 0.0000054 + 0.00055
        assert float(invocation.total_cost) == pytest.approx(0.000825, abs=1e-9)
        assert float(invocation.input_cost) == pytest.approx(0.00027, abs=1e-9)

        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.llm_call_count == 1
        assert reloaded.input_tokens == 1000
        assert reloaded.output_tokens == 500
        assert reloaded.cached_input_tokens == 200
        assert reloaded.reasoning_tokens == 50
        assert reloaded.total_tokens == 1700
        assert float(reloaded.total_cost) > 0


def test_unknown_model_cost_is_flagged_not_faked(app):
    with app.app_context():
        run = _make_run()
        provider = _Provider()
        provider.model = "mystery-model-9000"

        record_invocation(
            run,
            provider=provider,
            operation="agent_analysis",
            status="success",
            input_tokens=100,
            output_tokens=100,
            total_tokens=200,
            usage_source=USAGE_SOURCE_ESTIMATED,
        )
        db.session.commit()

        invocation = LLMInvocation.query.filter_by(run_id=run.id).one()
        assert invocation.usage_source == USAGE_SOURCE_ESTIMATED
        assert invocation.pricing_version is None
        assert float(invocation.total_cost) == 0.0, "未知价格不得伪造成本"


def test_planner_and_analysis_both_accumulate_on_run(app):
    with app.app_context():
        run = _make_run()
        record_invocation(run, provider=_Provider(), operation="planner", status="success", total_tokens=10)
        record_invocation(run, provider=_Provider(), operation="agent_analysis", status="success", total_tokens=20)
        db.session.commit()

        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.llm_call_count == 2
        assert reloaded.total_tokens == 30


def test_cost_service_summary_honest_sources(app):
    with app.app_context():
        run = _priced_run(app)
        record_invocation(
            run,
            provider=_Provider(),
            operation="planner",
            status="success",
            total_tokens=100,
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED,
        )
        unknown_provider = _Provider()
        unknown_provider.model = "no-price-model"
        record_invocation(
            run,
            provider=unknown_provider,
            operation="agent_analysis",
            status="failed",
            warning_code="LLM_PROVIDER_TIMEOUT",
            total_tokens=50,
            usage_source=USAGE_SOURCE_UNKNOWN,
        )
        db.session.commit()

        payload = run_costs(run)
        summary = payload["summary"]
        assert summary["calls"] == 2
        assert summary["total_tokens"] == 150
        assert summary["usage_sources"] == {"provider_reported": 1, "estimated": 0, "unknown": 1}
        assert summary["cost_source"] == "mixed"
        assert summary["cost_known"] is True
        assert len(payload["invocations"]) == 2
        assert payload["invocations"][0]["operation"] == "planner"
        assert "warning_code" in payload["invocations"][1]
