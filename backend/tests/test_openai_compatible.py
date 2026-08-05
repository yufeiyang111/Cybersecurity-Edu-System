import json

from app.services.llm.contracts import LLMRequest
from app.services.llm.openai_compatible import OpenAICompatibleProvider


class _FakeResponse:
    def __init__(self, *, status_code=200, payload=None, lines=None):
        self.status_code = status_code
        self._payload = payload
        self._lines = lines or []
        self.content = json.dumps(payload or {}).encode("utf-8")

    def json(self):
        return self._payload

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def test_generate_normalizes_openai_chat_completion_response():
    client = _FakeClient(
        _FakeResponse(
            payload={
                "model": "private-model-v2",
                "choices": [{"message": {"content": "safe answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
            }
        )
    )
    provider = OpenAICompatibleProvider(
        provider_name="private",
        base_url="https://llm.example/v1",
        api_key="private-api-key",
        model="private-model",
        http_client=client,
    )

    response = provider.generate(LLMRequest(prompt="hello", system_prompt="be safe"))

    assert response.is_success
    assert response.text == "safe answer"
    assert response.model == "private-model-v2"
    assert response.usage["total_tokens"] == 15
    args, kwargs = client.calls[0]
    assert args[0] == "https://llm.example/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer private-api-key"
    assert kwargs["json"]["messages"][0] == {"role": "system", "content": "be safe"}


def test_generate_stream_yields_content_and_finished_chunk():
    lines = [
        'data: {"choices":[{"delta":{"content":"safe "}}]}',
        'data: {"choices":[{"delta":{"content":"answer"}}]}',
        "data: [DONE]",
    ]
    client = _FakeClient(_FakeResponse(lines=lines))
    provider = OpenAICompatibleProvider(
        provider_name="private",
        base_url="https://llm.example/v1",
        api_key="private-api-key",
        model="private-model",
        http_client=client,
    )

    chunks = list(provider.generate_stream(LLMRequest(prompt="hello")))

    assert [chunk.delta for chunk in chunks] == ["safe ", "answer", ""]
    assert chunks[-1].finished is True
    assert chunks[-1].warning_code is None
    assert client.calls[0][1]["json"]["stream"] is True


def test_generate_returns_safe_warning_for_non_success_response():
    client = _FakeClient(_FakeResponse(status_code=401, payload={"error": "secret body"}))
    provider = OpenAICompatibleProvider(
        provider_name="private",
        base_url="https://llm.example/v1",
        api_key="private-api-key",
        model="private-model",
        http_client=client,
    )

    response = provider.generate(LLMRequest(prompt="hello"))

    assert response.text is None
    assert response.warning_code == "LLM_PROVIDER_NON_SUCCESS"
    assert "secret body" not in repr(response)
