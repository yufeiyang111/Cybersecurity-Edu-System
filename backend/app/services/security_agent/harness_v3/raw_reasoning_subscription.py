# -*- coding: utf-8 -*-
"""Provider 原始 reasoning 的活动 SSE 订阅对象。"""
from __future__ import annotations

from queue import Empty, Queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .raw_reasoning import (
        ProviderRawReasoningEnvelope,
        ProviderRawReasoningRelay,
    )

_MAX_DRAIN_DELTAS = 64


class ProviderRawReasoningSubscription:
    """一条活动 SSE 连接的瞬时订阅；关闭后不支持回放。"""

    def __init__(
        self,
        relay: ProviderRawReasoningRelay,
        *,
        topic: tuple[int, int],
        subscription_id: str,
        local_queue: Queue,
        pubsub: object | None,
    ) -> None:
        self._relay = relay
        self._topic = topic
        self._subscription_id = subscription_id
        self._local_queue = local_queue
        self._pubsub = pubsub
        self._closed = False

    def drain(
        self,
        maximum: int = _MAX_DRAIN_DELTAS,
    ) -> tuple[ProviderRawReasoningEnvelope, ...]:
        """读取当前已经到达的瞬时片段，不等待、不缓存未来片段。"""
        if self._closed:
            return ()
        limit = max(1, min(int(maximum), _MAX_DRAIN_DELTAS))
        entries: list[ProviderRawReasoningEnvelope] = []
        while len(entries) < limit:
            try:
                entries.append(self._local_queue.get_nowait())
            except Empty:
                break
        while len(entries) < limit and self._pubsub is not None:
            try:
                message = self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=0,
                )
            except Exception:  # Redis 瞬时通道不可用时安全降级为本进程队列。
                self._close_pubsub()
                break
            envelope = self._relay.decode_pubsub_message(message, self._topic)
            if envelope is None:
                break
            entries.append(envelope)
        return tuple(entries)

    def close(self) -> None:
        """断开活动订阅；已存在和后续 raw delta 均不再保留。"""
        if self._closed:
            return
        self._closed = True
        self._relay.unsubscribe(self._topic, self._subscription_id)
        self._close_pubsub()

    def _close_pubsub(self) -> None:
        pubsub = self._pubsub
        self._pubsub = None
        if pubsub is None:
            return
        try:
            pubsub.close()
        except Exception:
            return
