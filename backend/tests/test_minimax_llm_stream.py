"""MiniMaxLLM.chat_stream 流式接口单元测试（不发起真实网络请求）"""
from __future__ import annotations

from app.services.minimax_llm import MiniMaxLLM


class _FakeStreamResponse:
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self, decode_unicode=False):
        for line in self._lines:
            yield line


def _mock_post(monkeypatch, response):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, stream=None):
        captured.update({"url": url, "payload": json, "timeout": timeout, "stream": stream})
        return response

    monkeypatch.setattr("app.services.minimax_llm.requests.post", fake_post)
    return captured


def test_chat_stream_parses_sse_deltas_and_reasoning(monkeypatch):
    client = MiniMaxLLM(api_key="test-key", model="MiniMax-test")
    lines = [
        'data: {"choices":[{"delta":{"content":"你"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"reasoning_content":"想"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":"好"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
    ]
    captured = _mock_post(monkeypatch, _FakeStreamResponse(lines))

    events = list(
        client.chat_stream(
            [{"role": "user", "content": "你好"}],
            temperature=0.3,
            max_tokens=64,
            timeout_seconds=30,
        )
    )

    assert [e["delta"] for e in events] == ["你", "", "好", ""]
    assert [e["reasoning_delta"] for e in events] == ["", "想", "", ""]
    assert events[-1]["finish"] is True
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["model"] == "MiniMax-test"
    assert captured["timeout"] == 30
    assert captured["stream"] is True


def test_chat_stream_skips_keepalive_and_ignores_non_sse_lines(monkeypatch):
    client = MiniMaxLLM(api_key="test-key", model="MiniMax-test")
    lines = [
        ": keep-alive",
        "plain line",
        'data: {"choices":[{"delta":{"content":"A"},"finish_reason":null}]}',
        'data: [DONE]',
        'data: {"choices":[{"delta":{"content":"B"},"finish_reason":"stop"}]}',
    ]
    _mock_post(monkeypatch, _FakeStreamResponse(lines))

    events = list(client.chat_stream([{"role": "user", "content": "x"}]))

    assert "".join(e["delta"] for e in events) == "AB"
    assert events[-1]["finish"] is True


def test_chat_stream_stops_at_first_finish(monkeypatch):
    client = MiniMaxLLM(api_key="test-key", model="MiniMax-test")
    lines = [
        'data: {"choices":[{"delta":{"content":"A"},"finish_reason":"stop"}]}',
        'data: {"choices":[{"delta":{"content":"LATE"},"finish_reason":null}]}',
    ]
    _mock_post(monkeypatch, _FakeStreamResponse(lines))

    events = list(client.chat_stream([{"role": "user", "content": "x"}]))

    assert len(events) == 1
    assert events[0]["finish"] is True
    assert events[0]["delta"] == "A"


def test_chat_stream_non_success_status_yields_single_finish_event(monkeypatch):
    client = MiniMaxLLM(api_key="test-key", model="MiniMax-test")
    _mock_post(monkeypatch, _FakeStreamResponse([], status_code=500))

    events = list(client.chat_stream([{"role": "user", "content": "x"}]))

    assert len(events) == 1
    assert events[0]["status_code"] == 500
    assert events[0]["finish"] is True


def test_chat_stream_timeout_yields_safe_finish_event(monkeypatch):
    import requests

    client = MiniMaxLLM(api_key="test-key", model="MiniMax-test")

    def failing_post(*args, **kwargs):
        raise requests.exceptions.Timeout("timeout details")

    monkeypatch.setattr("app.services.minimax_llm.requests.post", failing_post)

    events = list(client.chat_stream([{"role": "user", "content": "x"}]))

    assert len(events) == 1
    assert events[0]["status_code"] == 408
    assert events[0]["finish"] is True
