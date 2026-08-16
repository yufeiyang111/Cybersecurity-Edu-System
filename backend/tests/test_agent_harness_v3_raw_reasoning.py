# -*- coding: utf-8 -*-
"""Harness V3 Provider 原始 reasoning 瞬时通道测试。"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_items import AgentItem
from app.models.agent_runtime import AgentMessage
from app.services.llm.contracts import LLMRequest, LLMStreamChunk
from app.services.security_agent.harness_v3.deep_review_provider import (
    DeepReviewProviderInvoker,
)
from app.services.security_agent.harness_v3.raw_reasoning import (
    PROVIDER_RAW_REASONING_EVENT,
    ProviderRawReasoningRelay,
    provider_raw_reasoning_frame,
)

from test_agent_harness_v3_deep_review import _make_v3_run


_RAW_REASONING = "Provider 原始 reasoning：逐步检查受限代码窗口。"


class _StreamingProvider:
    provider_name = "streaming-provider"
    model = "test-model"

    def generate_stream(self, _request):
        yield LLMStreamChunk(reasoning_delta=_RAW_REASONING)
        yield LLMStreamChunk(
            delta='{"title":"安全候选","summary":"仅用于测试"}',
            usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        )
        yield LLMStreamChunk(finished=True)


class _FallbackMustNotRun:
    @staticmethod
    def generate_with_failover(**_kwargs):
        raise AssertionError("流式 Provider 成功时不应退回普通 generate 路径")


def _enable_raw_reasoning(run) -> None:
    flags = dict(run.feature_flags_snapshot_json or {})
    flags["harness_v3"] = True
    flags["provider_raw_reasoning_stream"] = True
    run.feature_flags_snapshot_json = flags
    db.session.commit()


def test_raw_reasoning_relay_only_delivers_to_creator_live_subscription_and_never_replays(
    app,
    tmp_path,
):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        _enable_raw_reasoning(run)
        relay = ProviderRawReasoningRelay(redis_factory=lambda: None)

        creator = relay.subscribe(run, run.created_by)
        outsider = relay.subscribe(run, run.created_by + 1)

        assert creator is not None
        assert outsider is None
        assert relay.publish(run, run.created_by, _RAW_REASONING) is True

        envelopes = creator.drain()
        assert [envelope.delta for envelope in envelopes] == [_RAW_REASONING]
        frame = provider_raw_reasoning_frame(envelopes[0])
        assert f"event: {PROVIDER_RAW_REASONING_EVENT}" in frame
        assert "id:" not in frame
        assert '"transient": true' in frame

        creator.close()
        replacement = relay.subscribe(run, run.created_by)
        assert replacement is not None
        assert replacement.drain() == ()

        assert AgentEvent.query.filter_by(run_id=run.id).count() == 0
        assert AgentItem.query.filter_by(run_id=run.id).count() == 0
        assert AgentMessage.query.filter_by(run_id=run.id).count() == 0
        replacement.close()


def test_streaming_deep_review_forwards_only_provider_delta_without_persisting_raw_reasoning(
    app,
    tmp_path,
):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        _enable_raw_reasoning(run)
        relay = ProviderRawReasoningRelay(redis_factory=lambda: None)
        subscription = relay.subscribe(run, run.created_by)
        assert subscription is not None

        response, used = DeepReviewProviderInvoker(relay=relay).invoke(
            run=run,
            candidates=[_StreamingProvider()],
            request=LLMRequest(prompt="仅用于测试"),
            router=_FallbackMustNotRun(),
            trace_id="raw-reasoning-test",
            operation="agent_deep_review",
        )

        assert used.provider_name == "streaming-provider"
        assert response.text == '{"title":"安全候选","summary":"仅用于测试"}'
        assert response.reasoning is None
        assert response.usage["total_tokens"] == 18
        assert [entry.delta for entry in subscription.drain()] == [_RAW_REASONING]
        assert AgentEvent.query.filter_by(run_id=run.id).count() == 0
        assert AgentItem.query.filter_by(run_id=run.id).count() == 0
        assert AgentMessage.query.filter_by(run_id=run.id).count() == 0
        subscription.close()

class _OneShotSubscription:
    def __init__(self, envelope) -> None:
        self._envelope = envelope
        self._drained = False

    def drain(self):
        if self._drained:
            return ()
        self._drained = True
        return (self._envelope,)


def test_agent_event_stream_emits_transient_raw_frame_without_sequence_or_replay_state(
    app,
    tmp_path,
):
    from app.models.agent_runtime import AgentRunStatus
    from app.services.security_agent.sse import agent_event_stream

    with app.app_context():
        run = _make_v3_run(tmp_path)
        _enable_raw_reasoning(run)
        run.status = AgentRunStatus.COMPLETED.value
        db.session.commit()
        relay = ProviderRawReasoningRelay(redis_factory=lambda: None)
        subscription = relay.subscribe(run, run.created_by)
        assert subscription is not None
        relay.publish(run, run.created_by, _RAW_REASONING)
        envelope = subscription.drain()[0]
        subscription.close()

        stream = agent_event_stream(
            run.id,
            0,
            heartbeat_seconds=60,
            poll_seconds=0,
            raw_subscription=_OneShotSubscription(envelope),
        )
        frames = tuple(stream)

        assert len(frames) == 1
        assert f"event: {PROVIDER_RAW_REASONING_EVENT}" in frames[0]
        assert "id:" not in frames[0]
        assert _RAW_REASONING in frames[0]
        assert AgentEvent.query.filter_by(run_id=run.id).count() == 0

class _FakePubSub:
    def __init__(self, broker) -> None:
        self._broker = broker
        self._messages = []
        self._closed = False

    def subscribe(self, channel) -> None:
        self._broker.subscribers.setdefault(channel, []).append(self)

    def get_message(self, **_kwargs):
        if self._closed or not self._messages:
            return None
        return self._messages.pop(0)

    def close(self) -> None:
        self._closed = True


class _FakeRedisBroker:
    def __init__(self) -> None:
        self.subscribers = {}

    def pubsub(self, **_kwargs):
        return _FakePubSub(self)

    def publish(self, channel, payload) -> None:
        for subscriber in self.subscribers.get(channel, []):
            subscriber._messages.append({"data": payload})


class _PlainProvider:
    provider_name = "plain-provider"
    model = "test-model"


class _NonStreamingFallback:
    def __init__(self, response, provider) -> None:
        self._response = response
        self._provider = provider

    def generate_with_failover(self, **_kwargs):
        return self._response, self._provider, []


def test_raw_reasoning_cross_process_bridge_uses_ephemeral_pubsub_only(app, tmp_path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        _enable_raw_reasoning(run)
        broker = _FakeRedisBroker()
        sender = ProviderRawReasoningRelay(
            redis_factory=lambda: broker,
            process_id="sender",
        )
        receiver = ProviderRawReasoningRelay(
            redis_factory=lambda: broker,
            process_id="receiver",
        )
        subscription = receiver.subscribe(run, run.created_by)
        assert subscription is not None

        sender.publish(run, run.created_by, _RAW_REASONING)

        assert [entry.delta for entry in subscription.drain()] == [_RAW_REASONING]
        assert AgentEvent.query.filter_by(run_id=run.id).count() == 0
        subscription.close()


def test_non_streaming_provider_reasoning_is_forwarded_as_one_transient_delta(app, tmp_path):
    from app.services.llm.contracts import LLMResponse

    with app.app_context():
        run = _make_v3_run(tmp_path)
        _enable_raw_reasoning(run)
        relay = ProviderRawReasoningRelay(redis_factory=lambda: None)
        subscription = relay.subscribe(run, run.created_by)
        assert subscription is not None
        provider = _PlainProvider()
        response = LLMResponse(
            text='{"title":"安全候选"}',
            provider_name=provider.provider_name,
            model=provider.model,
            reasoning=_RAW_REASONING,
        )

        resolved, used = DeepReviewProviderInvoker(relay=relay).invoke(
            run=run,
            candidates=[provider],
            request=LLMRequest(prompt="仅用于测试"),
            router=_NonStreamingFallback(response, provider),
            trace_id="raw-reasoning-fallback",
            operation="agent_deep_review",
        )

        assert resolved is response
        assert used is provider
        assert [entry.delta for entry in subscription.drain()] == [_RAW_REASONING]
        assert AgentEvent.query.filter_by(run_id=run.id).count() == 0
        subscription.close()
