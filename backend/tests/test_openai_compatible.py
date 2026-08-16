import json
import logging

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



def test_generate_logs_only_response_metadata_without_sensitive_content(app, caplog):
    prompt_secret = "prompt-secret-must-not-be-logged"
    system_secret = "system-secret-must-not-be-logged"
    response_secret = "response-secret-must-not-be-logged"
    api_key_secret = "api-key-secret-must-not-be-logged"
    private_endpoint = "https://private-llm.internal/v1"
    model_secret = "private-model-must-not-be-logged"
    client = _FakeClient(
        _FakeResponse(
            payload={
                "model": model_secret,
                "choices": [
                    {
                        "message": {"content": response_secret},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
    )
    provider = OpenAICompatibleProvider(
        provider_name="private",
        base_url=private_endpoint,
        api_key=api_key_secret,
        model=model_secret,
        http_client=client,
    )

    with app.app_context(), caplog.at_level(logging.DEBUG, logger=app.logger.name):
        response = provider.generate(
            LLMRequest(
                prompt=prompt_secret,
                system_prompt=system_secret,
            )
        )

    assert response.is_success
    assert response.text == response_secret
    assert "OpenAICompatibleProvider HTTP response metadata" in caplog.text
    assert "response_bytes=" in caplog.text
    assert "response_sha256=" in caplog.text
    for secret in (
        prompt_secret,
        system_secret,
        response_secret,
        api_key_secret,
        private_endpoint,
        model_secret,
    ):
        assert secret not in caplog.text

def test_generate_empty_content_logs_no_raw_provider_body(app, caplog):
    response_secret = "empty-content-secret-must-not-be-logged"
    api_key_secret = "empty-api-key-secret-must-not-be-logged"
    private_endpoint = "https://empty-provider.internal/v1"
    model_secret = "empty-model-secret-must-not-be-logged"
    client = _FakeClient(
        _FakeResponse(
            payload={
                "model": model_secret,
                "choices": [
                    {
                        "message": {
                            "content": f"<think>{response_secret}</think>",
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
        )
    )
    provider = OpenAICompatibleProvider(
        provider_name="private",
        base_url=private_endpoint,
        api_key=api_key_secret,
        model=model_secret,
        http_client=client,
    )

    with app.app_context(), caplog.at_level(logging.DEBUG, logger=app.logger.name):
        response = provider.generate(LLMRequest(prompt="empty-content-prompt"))

    assert response.is_success is False
    assert response.warning_code == "LLM_OUTPUT_INVALID"
    assert "OpenAICompatible empty response metadata" in caplog.text
    for secret in (
        response_secret,
        api_key_secret,
        private_endpoint,
        model_secret,
        "empty-content-prompt",
    ):
        assert secret not in caplog.text

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


def test_generate_stream_keeps_utf8_chinese_intact():
    lines = [
        'data: {"choices":[{"delta":{"content":"安全"}}]}'.encode("utf-8"),
        'data: {"choices":[{"delta":{"content":"分析"}}]}'.encode("utf-8"),
        "data: [DONE]".encode("utf-8"),
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

    assert [chunk.delta for chunk in chunks] == ["安全", "分析", ""]
    assert chunks[-1].finished is True


def test_generate_stream_auto_repairs_latin1_mojibake():
    def broken_line(text):
        return 'data: {"choices":[{"delta":{"content":"%s"}}]}' % text

    broken = "安全分析".encode("utf-8").decode("latin-1")
    lines = [
        broken_line(broken).encode("utf-8"),
        "data: [DONE]".encode("utf-8"),
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

    assert chunks[0].delta == "安全分析"


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
