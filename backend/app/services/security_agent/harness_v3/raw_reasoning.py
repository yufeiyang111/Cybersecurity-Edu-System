# -*- coding: utf-8 -*-
"""Harness V3 Provider 原始 reasoning 的瞬时中继。

该模块只负责任务发起人的活动 SSE 订阅：不写数据库、不写 AgentEvent、
不写日志、不保存历史。跨进程仅使用 Redis Pub/Sub，传输失败时直接丢弃。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from queue import Full, Queue
from threading import RLock
from typing import Callable
from uuid import uuid4

from flask import current_app, has_app_context

from app.models.agent_runtime import AgentRun
from app.services.security_agent.feature_flags import AgentFeatureFlags
from app.services.security_agent.harness_v3.raw_reasoning_subscription import (
    ProviderRawReasoningSubscription,
)

PROVIDER_RAW_REASONING_EVENT = "provider_reasoning_raw_delta"
_MAX_PENDING_DELTAS = 64


@dataclass(frozen=True)
class ProviderRawReasoningEnvelope:
    """一条仅供当前连接展示的 Provider 原始 reasoning delta。"""

    run_id: int
    recipient_user_id: int
    delta: str
    source: str = "provider"


class ProviderRawReasoningRelay:
    """受 Feature Flag 与所有权约束的非持久化 Provider reasoning 通道。"""

    def __init__(
        self,
        *,
        redis_factory: Callable[[], object | None] | None = None,
        process_id: str | None = None,
    ) -> None:
        self._redis_factory = redis_factory
        self._process_id = process_id or f"{os.getpid()}-{uuid4().hex}"
        self._subscriptions: dict[tuple[int, int], dict[str, Queue]] = {}
        self._lock = RLock()

    def can_stream(self, run: AgentRun, recipient_user_id: int | None) -> bool:
        """原始片段仅允许 V3 Run 的发起人接收，现有 Route 仍负责读取鉴权。"""
        if recipient_user_id is None or run.created_by != recipient_user_id:
            return False
        mode = getattr(getattr(run, "mode", None), "value", getattr(run, "mode", ""))
        if mode not in {"hybrid", "deep_audit"}:
            return False
        flags = AgentFeatureFlags().for_run(run)
        return bool(flags.harness_v3 and flags.provider_raw_reasoning_stream)

    def subscribe(
        self,
        run: AgentRun,
        recipient_user_id: int | None,
    ) -> ProviderRawReasoningSubscription | None:
        """注册当前 SSE 连接；未授权或关闭时不创建任何缓存。"""
        if not self.can_stream(run, recipient_user_id):
            return None
        topic = (run.id, int(recipient_user_id))
        subscription_id = uuid4().hex
        local_queue: Queue = Queue(maxsize=_MAX_PENDING_DELTAS)
        with self._lock:
            self._subscriptions.setdefault(topic, {})[subscription_id] = local_queue
        return ProviderRawReasoningSubscription(
            self,
            topic=topic,
            subscription_id=subscription_id,
            local_queue=local_queue,
            pubsub=self._create_pubsub(topic),
        )

    def unsubscribe(self, topic: tuple[int, int], subscription_id: str) -> None:
        """仅移除当前连接的内存队列，不保留任何回放缓冲。"""
        with self._lock:
            subscribers = self._subscriptions.get(topic)
            if subscribers is None:
                return
            subscribers.pop(subscription_id, None)
            if not subscribers:
                self._subscriptions.pop(topic, None)

    def publish(
        self,
        run: AgentRun,
        recipient_user_id: int | None,
        delta: str,
    ) -> bool:
        """投递 Provider 明确返回的原始 delta；无人订阅时直接丢弃。"""
        if not isinstance(delta, str) or not delta or not self.can_stream(run, recipient_user_id):
            return False
        envelope = ProviderRawReasoningEnvelope(
            run_id=run.id,
            recipient_user_id=int(recipient_user_id),
            delta=delta,
        )
        topic = (envelope.run_id, envelope.recipient_user_id)
        self._publish_local(topic, envelope)
        self._publish_pubsub(topic, envelope)
        return True

    def decode_pubsub_message(
        self,
        message: object,
        topic: tuple[int, int],
    ) -> ProviderRawReasoningEnvelope | None:
        """仅接纳目标 topic 的其他进程瞬时 Pub/Sub 消息。"""
        if not isinstance(message, dict):
            return None
        raw_data = message.get("data")
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8", errors="ignore")
        if not isinstance(raw_data, str):
            return None
        try:
            payload = json.loads(raw_data)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("origin") == self._process_id:
            return None
        if payload.get("run_id") != topic[0] or payload.get("recipient_user_id") != topic[1]:
            return None
        delta = payload.get("delta")
        if not isinstance(delta, str) or not delta:
            return None
        return ProviderRawReasoningEnvelope(
            run_id=topic[0],
            recipient_user_id=topic[1],
            delta=delta,
        )

    def _publish_local(
        self,
        topic: tuple[int, int],
        envelope: ProviderRawReasoningEnvelope,
    ) -> None:
        with self._lock:
            queues = tuple(self._subscriptions.get(topic, {}).values())
        for local_queue in queues:
            try:
                local_queue.put_nowait(envelope)
            except Full:
                continue

    def _create_pubsub(self, topic: tuple[int, int]) -> object | None:
        client = self._redis_client()
        if client is None:
            return None
        try:
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(self._channel(topic))
            return pubsub
        except Exception:
            return None

    def _publish_pubsub(
        self,
        topic: tuple[int, int],
        envelope: ProviderRawReasoningEnvelope,
    ) -> None:
        client = self._redis_client()
        if client is None:
            return
        payload = json.dumps(
            {
                "origin": self._process_id,
                "run_id": envelope.run_id,
                "recipient_user_id": envelope.recipient_user_id,
                "delta": envelope.delta,
            },
            ensure_ascii=False,
        )
        try:
            client.publish(self._channel(topic), payload)
        except Exception:
            return

    def _redis_client(self) -> object | None:
        if self._redis_factory is not None:
            try:
                return self._redis_factory()
            except Exception:
                return None
        if not has_app_context() or not current_app.config.get("RQ_ASYNC", False):
            return None
        redis_url = str(current_app.config.get("REDIS_URL", "")).strip()
        if not redis_url:
            return None
        try:
            from redis import Redis

            return Redis.from_url(
                redis_url,
                socket_timeout=0.1,
                socket_connect_timeout=0.1,
            )
        except Exception:
            return None

    @staticmethod
    def _channel(topic: tuple[int, int]) -> str:
        return f"cyberguard:agent:raw-reasoning:{topic[0]}:{topic[1]}"


def provider_raw_reasoning_frame(envelope: ProviderRawReasoningEnvelope) -> str:
    """构造无 SSE id 的瞬时帧，不能推进 Last-Event-ID 水位。"""
    payload = {
        "run_id": envelope.run_id,
        "delta": envelope.delta,
        "transient": True,
        "source": envelope.source,
    }
    return (
        f"event: {PROVIDER_RAW_REASONING_EVENT}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


_default_relay = ProviderRawReasoningRelay()


def get_provider_raw_reasoning_relay() -> ProviderRawReasoningRelay:
    """返回进程级瞬时中继；其内存内容不跨请求、进程或重启保留。"""
    return _default_relay
