# -*- coding: utf-8 -*-
"""Persistence models for agent-run LLM invocations and versioned price catalog."""
from __future__ import annotations

from datetime import datetime

from app import db


class LLMInvocation(db.Model):
    """One LLM call made by an agent run, with token usage and cost audit."""

    __tablename__ = "llm_invocations"
    __table_args__ = (
        db.Index("ix_llm_invocations_run_created", "run_id", "created_at"),
        db.Index("ix_llm_invocations_workspace_created", "workspace_id", "created_at"),
        db.Index("ix_llm_invocations_user_created", "user_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    step_execution_id = db.Column(db.Integer, db.ForeignKey("agent_step_executions.id", ondelete="SET NULL"))
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    provider_config_id = db.Column(db.Integer, db.ForeignKey("llm_provider_configs.id", ondelete="SET NULL"))
    provider_name = db.Column(db.String(128), nullable=False)
    model = db.Column(db.String(200))
    model_version = db.Column(db.String(64))
    operation = db.Column(db.String(64), nullable=False, default="unknown")
    prompt_template_version = db.Column(db.String(64))
    input_digest = db.Column(db.String(64))
    output_digest = db.Column(db.String(64))
    status = db.Column(db.String(32), nullable=False)
    warning_code = db.Column(db.String(100))
    latency_ms = db.Column(db.Integer)
    first_token_latency_ms = db.Column(db.Integer)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    cached_input_tokens = db.Column(db.Integer, nullable=False, default=0)
    cache_creation_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    reasoning_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    usage_source = db.Column(db.String(24), nullable=False, default="unknown")
    currency = db.Column(db.String(8), nullable=False, default="USD")
    input_cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    cached_input_cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    output_cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    reasoning_cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    total_cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    pricing_version = db.Column(db.String(64))
    provider_cache_hit = db.Column(db.Boolean, nullable=False, default=False)
    application_cache_hit = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_execution_id": self.step_execution_id,
            "provider_config_id": self.provider_config_id,
            "provider_name": self.provider_name,
            "model": self.model,
            "model_version": self.model_version,
            "operation": self.operation,
            "prompt_template_version": self.prompt_template_version,
            "status": self.status,
            "warning_code": self.warning_code,
            "latency_ms": self.latency_ms,
            "first_token_latency_ms": self.first_token_latency_ms,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
            "currency": self.currency,
            "input_cost": float(self.input_cost or 0),
            "cached_input_cost": float(self.cached_input_cost or 0),
            "output_cost": float(self.output_cost or 0),
            "reasoning_cost": float(self.reasoning_cost or 0),
            "total_cost": float(self.total_cost or 0),
            "pricing_version": self.pricing_version,
            "provider_cache_hit": bool(self.provider_cache_hit),
            "application_cache_hit": bool(self.application_cache_hit),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LLMPriceCatalog(db.Model):
    """Versioned price snapshot for one provider/model (per million tokens)."""

    __tablename__ = "llm_price_catalog"
    __table_args__ = (
        db.UniqueConstraint(
            "provider_name",
            "model",
            "currency",
            "pricing_version",
            name="uq_llm_price_catalog_entry",
        ),
        db.Index("ix_llm_price_catalog_model", "model"),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(128), nullable=False)
    model = db.Column(db.String(200), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    input_price_per_million = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    cached_input_price_per_million = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    output_price_per_million = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    reasoning_price_per_million = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    pricing_version = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(32), nullable=False, default="builtin")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider_name": self.provider_name,
            "model": self.model,
            "currency": self.currency,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "input_price_per_million": float(self.input_price_per_million or 0),
            "cached_input_price_per_million": float(self.cached_input_price_per_million or 0),
            "output_price_per_million": float(self.output_price_per_million or 0),
            "reasoning_price_per_million": float(self.reasoning_price_per_million or 0),
            "pricing_version": self.pricing_version,
            "source": self.source,
        }
