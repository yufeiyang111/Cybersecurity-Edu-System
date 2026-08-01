from __future__ import annotations

from app.services.rate_limit import RateLimiter


def test_rate_limiter_blocks_after_window_limit_without_exposing_key(monkeypatch):
    limiter = RateLimiter()
    monkeypatch.setattr(limiter, "_allow_redis", lambda key, limit, window_seconds: None)

    first = limiter.allow("user-1:127.0.0.1", 1, 60)
    second = limiter.allow("user-1:127.0.0.1", 1, 60)

    assert first.allowed is True
    assert second.allowed is False
    assert second.retry_after >= 1
    assert "user-1" not in repr(second)