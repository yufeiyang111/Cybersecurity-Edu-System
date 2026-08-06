"""Unit tests for cache-aware usage normalization (learned from LabexAgent)."""
from app.services.llm.usage_normalizer import (
    CACHE_STATUS_HIT,
    CACHE_STATUS_MISS,
    CACHE_STATUS_NOT_REPORTED,
    CACHE_STATUS_WRITE_ONLY,
    cache_status,
    normalize_usage,
)


def test_normalize_openai_style_cached_tokens():
    normalized = normalize_usage(
        {
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "total_tokens": 150,
            "prompt_tokens_details": {"cached_tokens": 80},
        }
    )

    assert normalized["cached_tokens"] == 80
    assert normalized["cache_write_tokens"] == 0
    assert normalized["cache_usage_reported"] is True
    assert normalized["prompt_tokens"] == 120
    assert normalized["total_tokens"] == 150


def test_normalize_anthropic_style_cache_read():
    normalized = normalize_usage(
        {
            "input_tokens": 200,
            "output_tokens": 40,
            "input_token_details": {"cache_read": 150, "cache_creation": 50},
        }
    )

    assert normalized["prompt_tokens"] == 200
    assert normalized["cached_tokens"] == 150
    assert normalized["cache_write_tokens"] == 50
    assert normalized["cache_usage_reported"] is True


def test_normalize_flat_cache_fields():
    normalized = normalize_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
            "cache_read_input_tokens": 60,
        }
    )

    assert normalized["cached_tokens"] == 60
    assert normalized["cache_usage_reported"] is True


def test_normalize_returns_none_for_empty_or_missing_usage():
    assert normalize_usage(None) is None
    assert normalize_usage({}) is None
    assert normalize_usage({"unknown": "field"}) is None


def test_cache_status_mapping():
    assert cache_status(False, cached_tokens=0, cache_write_tokens=0) == CACHE_STATUS_NOT_REPORTED
    assert cache_status(True, cached_tokens=10, cache_write_tokens=0) == CACHE_STATUS_HIT
    assert cache_status(True, cached_tokens=0, cache_write_tokens=10) == CACHE_STATUS_WRITE_ONLY
    assert cache_status(True, cached_tokens=0, cache_write_tokens=0) == CACHE_STATUS_MISS
