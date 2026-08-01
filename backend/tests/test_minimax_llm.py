from __future__ import annotations

import json
import logging

import requests

from app.services import minimax_llm


class FakeResponse:
    def __init__(self, payload, *, status_code: int = 200, body: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.text = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError("provider-error-body-should-not-be-logged")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_chat_does_not_emit_prompt_api_key_or_raw_model_response(monkeypatch, caplog, capsys):
    prompt_secret = "prompt-secret-should-not-appear"
    api_key_secret = "api-key-secret-should-not-appear"
    response_secret = "model-response-secret-should-not-appear"
    model_secret = "model-secret-should-not-appear"
    endpoint_secret = "https://internal.example.invalid/private-route"
    captured_request = {}

    def fake_post(url, **kwargs):
        captured_request["url"] = url
        captured_request.update(kwargs)
        return FakeResponse(
            {
                "choices": [{"message": {"content": response_secret}}],
                "usage": {"total_tokens": 7},
                "provider_metadata": {"secret": "raw-metadata-should-not-escape"},
            }
        )

    monkeypatch.setattr(minimax_llm.requests, "post", fake_post)
    client = minimax_llm.MiniMaxLLM(api_key=api_key_secret, model=model_secret)
    client.api_base = endpoint_secret

    with caplog.at_level(logging.INFO, logger=minimax_llm.logger.name):
        result = client.chat([{"role": "user", "content": prompt_secret}])

    stdout, stderr = capsys.readouterr()
    logged = caplog.text

    assert result["output"]["choices"][0]["message"]["content"] == response_secret
    assert "raw" not in result
    assert captured_request["headers"]["Authorization"] == f"Bearer {api_key_secret}"
    for sensitive_value in (
        prompt_secret,
        api_key_secret,
        response_secret,
        model_secret,
        endpoint_secret,
        "raw-metadata-should-not-escape",
    ):
        assert sensitive_value not in logged
        assert sensitive_value not in stdout
        assert sensitive_value not in stderr


def test_chat_logs_only_safe_metadata_for_provider_error(monkeypatch, caplog, capsys):
    error_body_secret = "provider-error-body-should-not-be-logged"
    prompt_secret = "failed-prompt-should-not-appear"

    def fake_post(*_args, **_kwargs):
        return FakeResponse({}, status_code=500, body=error_body_secret)

    monkeypatch.setattr(minimax_llm.requests, "post", fake_post)
    client = minimax_llm.MiniMaxLLM(api_key="test-api-key", model="test-model")

    with caplog.at_level(logging.INFO, logger=minimax_llm.logger.name):
        result = client.chat([{"role": "user", "content": prompt_secret}])

    stdout, stderr = capsys.readouterr()
    logged = caplog.text

    assert result == {"status_code": 500, "message": "\u8bf7\u6c42\u5931\u8d25"}
    assert "status_code=500" in logged
    assert "error_type=HTTPError" in logged
    for sensitive_value in (error_body_secret, prompt_secret):
        assert sensitive_value not in logged
        assert sensitive_value not in stdout
        assert sensitive_value not in stderr


def test_chat_does_not_log_invalid_json_body(monkeypatch, caplog):
    invalid_body_secret = "invalid-json-body-should-not-be-logged"

    def fake_post(*_args, **_kwargs):
        return FakeResponse(
            json.JSONDecodeError("invalid JSON", invalid_body_secret, 0),
        )

    monkeypatch.setattr(minimax_llm.requests, "post", fake_post)
    client = minimax_llm.MiniMaxLLM(api_key="test-api-key", model="test-model")

    with caplog.at_level(logging.INFO, logger=minimax_llm.logger.name):
        result = client.chat([{"role": "user", "content": "safe-input"}])

    assert result == {"status_code": 500, "message": "\u54cd\u5e94JSON\u89e3\u6790\u5931\u8d25"}
    assert "invalid-json-body-should-not-be-logged" not in caplog.text
    assert "MiniMax API returned invalid JSON" in caplog.text

def test_chat_uses_configured_minimax_endpoint_and_model(monkeypatch):
    captured_request = {}

    def fake_post(url, **kwargs):
        captured_request["url"] = url
        captured_request.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(minimax_llm.requests, "post", fake_post)
    monkeypatch.setattr(minimax_llm.Config, "MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
    monkeypatch.setattr(minimax_llm.Config, "MINIMAX_MODEL", "MiniMax-M2.7")

    client = minimax_llm.MiniMaxLLM(api_key="test-api-key")
    client.chat([{"role": "user", "content": "safe input"}])

    assert minimax_llm.MiniMaxLLM.BASE_URL == "https://api.minimaxi.com/v1"
    assert captured_request["url"] == "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    assert captured_request["json"]["model"] == "MiniMax-M2.7"
