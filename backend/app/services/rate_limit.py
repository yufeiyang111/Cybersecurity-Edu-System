"""高成本安全 API 的轻量限流边界。"""
from __future__ import annotations

from collections import defaultdict
from functools import wraps
from threading import Lock
from time import monotonic
from typing import Callable

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity
from redis import Redis


class RateLimitDecision:
    def __init__(self, allowed: bool, retry_after: int) -> None:
        self.allowed = allowed
        self.retry_after = retry_after


class RateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._local: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
        self._redis: Redis | None = None

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitDecision:
        limit = max(1, int(limit))
        window_seconds = max(1, int(window_seconds))
        redis_decision = self._allow_redis(key, limit, window_seconds)
        if redis_decision is not None:
            return redis_decision
        now = monotonic()
        with self._lock:
            started, count = self._local[key]
            if now - started >= window_seconds:
                started, count = now, 0
            count += 1
            self._local[key] = (started, count)
            allowed = count <= limit
            retry_after = max(1, int(window_seconds - (now - started)))
            return RateLimitDecision(allowed, retry_after)

    def _allow_redis(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision | None:
        redis_url = str(current_app.config.get("REDIS_URL", "")).strip()
        if not redis_url:
            return None
        try:
            if self._redis is None:
                self._redis = Redis.from_url(redis_url, socket_timeout=0.2, socket_connect_timeout=0.2)
            redis_key = f"cyberguard:rate:{key}"
            count = int(self._redis.incr(redis_key))
            if count == 1:
                self._redis.expire(redis_key, window_seconds)
            ttl = int(self._redis.ttl(redis_key))
            return RateLimitDecision(count <= limit, max(1, ttl))
        except Exception:
            self._redis = None
            return None


def get_rate_limiter() -> RateLimiter:
    limiter = current_app.extensions.get("cyberguard_rate_limiter")
    if limiter is None:
        limiter = RateLimiter()
        current_app.extensions["cyberguard_rate_limiter"] = limiter
    return limiter


def rate_limit(scope: str, config_key: str, *, window_seconds: int = 60) -> Callable:
    """按已认证用户和来源地址限制高成本 API，不记录请求正文。"""
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                actor = str(get_jwt_identity())
            except Exception:
                actor = "anonymous"
            source = request.remote_addr or "unknown"
            key = f"{scope}:{actor}:{source}"
            limit = int(current_app.config.get(config_key, 10))
            decision = get_rate_limiter().allow(key, limit, window_seconds)
            if not decision.allowed:
                response = jsonify({"error": "请求过于频繁，请稍后重试"})
                response.status_code = 429
                response.headers["Retry-After"] = str(decision.retry_after)
                return response
            return view(*args, **kwargs)

        return wrapped

    return decorator