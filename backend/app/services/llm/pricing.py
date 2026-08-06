# -*- coding: utf-8 -*-
"""Versioned price catalog lookup and per-invocation cost calculation.

Costs are always explicit about their source:
- provider_reported: the provider reported a cost (future admin integrations).
- estimated: computed from the built-in price catalog snapshot.
- unknown: no price entry exists; total_cost stays 0 but must be displayed as
  unknown rather than a confident zero.
"""
from __future__ import annotations

from app import db
from app.models.agent_llm import LLMPriceCatalog

USAGE_SOURCE_PROVIDER_REPORTED = "provider_reported"
USAGE_SOURCE_ESTIMATED = "estimated"
USAGE_SOURCE_UNKNOWN = "unknown"

BUILTIN_PRICING_VERSION = "builtin-v1"
DEFAULT_CURRENCY = "USD"


def lookup_price(provider_name: str, model: str | None) -> LLMPriceCatalog | None:
    """Return the latest catalog entry for a provider/model, if any."""
    if not model:
        return None
    entry = (
        LLMPriceCatalog.query.filter_by(
            provider_name=provider_name,
            model=model,
            currency=DEFAULT_CURRENCY,
        )
        .order_by(LLMPriceCatalog.pricing_version.desc(), LLMPriceCatalog.id.desc())
        .first()
    )
    if entry is not None:
        return entry
    return (
        LLMPriceCatalog.query.filter_by(model=model, currency=DEFAULT_CURRENCY)
        .order_by(LLMPriceCatalog.pricing_version.desc(), LLMPriceCatalog.id.desc())
        .first()
    )


def calculate_cost(
    *,
    provider_name: str,
    model: str | None,
    input_tokens: int,
    cached_input_tokens: int,
    cache_creation_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    currency: str = DEFAULT_CURRENCY,
) -> dict:
    """Compute cost breakdown; returns usage_source and pricing_version too."""
    entry = lookup_price(provider_name, model)
    if entry is None:
        return {
            "usage_source": USAGE_SOURCE_UNKNOWN,
            "pricing_version": None,
            "currency": currency,
            "input_cost": 0.0,
            "cached_input_cost": 0.0,
            "output_cost": 0.0,
            "reasoning_cost": 0.0,
            "total_cost": 0.0,
        }
    input_cost = _cost(
        input_tokens,
        float(entry.input_price_per_million or 0),
    )
    cached_cost = _cost(
        cached_input_tokens,
        float(entry.cached_input_price_per_million or 0),
    )
    cache_creation_cost = _cost(
        cache_creation_tokens,
        float(entry.input_price_per_million or 0),
    )
    output_cost = _cost(
        output_tokens,
        float(entry.output_price_per_million or 0),
    )
    reasoning_cost = _cost(
        reasoning_tokens,
        float(entry.reasoning_price_per_million or 0),
    )
    total = round(input_cost + cached_cost + cache_creation_cost + output_cost + reasoning_cost, 6)
    return {
        "usage_source": USAGE_SOURCE_ESTIMATED,
        "pricing_version": entry.pricing_version,
        "currency": currency,
        "input_cost": round(input_cost, 6),
        "cached_input_cost": round(cached_cost, 6),
        "output_cost": round(output_cost, 6),
        "reasoning_cost": round(reasoning_cost, 6),
        "total_cost": total,
    }


def _cost(tokens: int, price_per_million: float) -> float:
    if tokens <= 0 or price_per_million <= 0:
        return 0.0
    return round(tokens * price_per_million / 1_000_000, 6)
