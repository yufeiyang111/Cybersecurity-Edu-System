"""Persistence models for user-managed LLM providers and safe call metadata."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


class LLMProviderConfig(db.Model):
    """A user-owned OpenAI-compatible LLM configuration."""

    __tablename__ = "llm_provider_configs"
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_llm_provider_configs_user_name"),
        db.Index("ix_llm_provider_configs_user_default", "user_id", "is_default"),
        db.Index("ix_llm_provider_configs_user_enabled", "user_id", "is_enabled"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    provider_type = db.Column(db.String(32), nullable=False, default="openai_compatible")
    base_url = db.Column(db.String(500), nullable=False)
    model = db.Column(db.String(200), nullable=False)
    api_key_ciphertext = db.Column(db.Text, nullable=False)
    api_key_hint = db.Column(db.String(64), nullable=False)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    max_tokens = db.Column(db.Integer)
    last_check_status = db.Column(db.String(32))
    last_checked_at = db.Column(db.DateTime)
    last_latency_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", foreign_keys=[user_id])
    call_logs = db.relationship("LLMCallLog", back_populates="provider_config")

    def to_dict(self) -> dict:
        """Return only fields safe for the authenticated user's UI."""
        return {
            "id": self.id,
            "name": self.name,
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_masked": self.api_key_hint,
            "is_enabled": bool(self.is_enabled),
            "is_default": bool(self.is_default),
            "max_tokens": self.max_tokens,
            "last_check_status": self.last_check_status,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_latency_ms": self.last_latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LLMCallLog(db.Model):
    """Non-sensitive metadata for one LLM call."""

    __tablename__ = "llm_call_logs"
    __table_args__ = (
        db.Index("ix_llm_call_logs_user_created", "user_id", "created_at"),
        db.Index("ix_llm_call_logs_user_model_created", "user_id", "model", "created_at"),
        db.Index(
            "ix_llm_call_logs_user_provider_created",
            "user_id",
            "provider_config_id",
            "created_at",
        ),
        db.Index("ix_llm_call_logs_user_status_created", "user_id", "status", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider_config_id = db.Column(
        db.Integer,
        db.ForeignKey("llm_provider_configs.id", ondelete="SET NULL"),
    )
    provider_name = db.Column(db.String(128), nullable=False)
    model = db.Column(db.String(200))
    operation = db.Column(db.String(64), nullable=False, default="unknown")
    status = db.Column(db.String(32), nullable=False)
    warning_code = db.Column(db.String(100))
    request_id = db.Column(db.String(64))
    streaming = db.Column(db.Boolean, nullable=False, default=False)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    cached_input_tokens = db.Column(db.Integer, nullable=False, default=0)
    cache_status = db.Column(db.String(16))
    cache_write_input_tokens = db.Column(db.Integer, nullable=False, default=0)
    reasoning_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    cost_amount = db.Column(db.Numeric(12, 6))
    currency = db.Column(db.String(8), nullable=False, default="USD")
    latency_ms = db.Column(db.Integer)
    first_token_latency_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    provider_config = db.relationship("LLMProviderConfig", back_populates="call_logs")

    def to_dict(self) -> dict:
        status = self.status.value if isinstance(self.status, Enum) else self.status
        return {
            "id": self.id,
            "provider_config_id": self.provider_config_id,
            "provider_name": self.provider_name,
            "model": self.model,
            "operation": self.operation,
            "status": status,
            "warning_code": self.warning_code,
            "request_id": self.request_id,
            "streaming": bool(self.streaming),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_status": self.cache_status,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "cost_amount": float(self.cost_amount) if self.cost_amount is not None else None,
            "currency": self.currency,
            "latency_ms": self.latency_ms,
            "first_token_latency_ms": self.first_token_latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
