from datetime import datetime, timedelta
import importlib
import sys

import pytest
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token

from app import db
from app.models.llm import LLMCallLog, LLMProviderConfig
from app.models.user import User


@pytest.fixture
def llm_api_app(tmp_path, monkeypatch):
    from conftest import TestConfig, _install_legacy_route_stubs
    from app import create_app

    _install_legacy_route_stubs(monkeypatch)
    monkeypatch.delitem(sys.modules, "app.routes.llm", raising=False)
    importlib.import_module("app.routes.llm")
    config = type(
        "LLMApiTestConfig",
        (TestConfig,),
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'llm_api.db'}",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "LLM_PROVIDER_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
            "LLM_PROVIDER_ALLOWED_HOSTS": ["llm.internal:8000"],
        },
    )
    application = create_app(config)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _make_user(application, username: str) -> int:
    with application.app_context():
        user = User(username=username, email=f"{username}@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        return user.id


def _headers(application, user_id: int) -> dict[str, str]:
    with application.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def test_llm_provider_api_requires_authentication(llm_api_app):
    response = llm_api_app.test_client().get("/api/llm/providers")

    assert response.status_code == 401


def test_user_can_create_list_and_update_provider_without_exposing_key(llm_api_app):
    user_id = _make_user(llm_api_app, "llm-api-user")
    client = llm_api_app.test_client()
    headers = _headers(llm_api_app, user_id)

    created = client.post(
        "/api/llm/providers",
        json={
            "name": "private",
            "base_url": "http://llm.internal:8000/v1",
            "model": "private-model",
            "api_key": "sk-private-secret",
            "is_default": True,
        },
        headers=headers,
    )

    assert created.status_code == 201
    payload = created.json["provider"]
    assert payload["is_default"] is True
    assert "sk-private-secret" not in repr(created.json)
    provider_id = payload["id"]

    listed = client.get("/api/llm/providers", headers=headers)
    assert listed.status_code == 200
    assert listed.json["providers"][0]["id"] == provider_id

    updated = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"name": "private-renamed", "api_key": ""},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json["provider"]["name"] == "private-renamed"
    assert updated.json["provider"]["api_key_masked"] == "sk-pr••••cret"


def test_user_cannot_access_another_users_provider(llm_api_app):
    owner_id = _make_user(llm_api_app, "llm-owner")
    outsider_id = _make_user(llm_api_app, "llm-outsider")
    with llm_api_app.app_context():
        provider = LLMProviderConfig(
            user_id=owner_id,
            name="private",
            base_url="http://llm.internal:8000/v1",
            model="private-model",
            api_key_ciphertext="ciphertext",
            api_key_hint="sk-pr••••cret",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id

    response = llm_api_app.test_client().get(
        f"/api/llm/providers/{provider_id}",
        headers=_headers(llm_api_app, outsider_id),
    )

    assert response.status_code == 404


def test_logs_are_paginated_and_analytics_are_scoped_to_current_user(llm_api_app):
    user_id = _make_user(llm_api_app, "llm-log-user")
    other_user_id = _make_user(llm_api_app, "llm-other-user")
    with llm_api_app.app_context():
        now = datetime.utcnow()
        db.session.add_all(
            [
                LLMCallLog(
                    user_id=user_id,
                    provider_name="private",
                    model="qwen",
                    operation="qa",
                    status="success",
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    cost_amount=0.12,
                    latency_ms=100,
                    created_at=now,
                ),
                LLMCallLog(
                    user_id=user_id,
                    provider_name="private",
                    model="qwen",
                    operation="qa",
                    status="failed",
                    warning_code="LLM_PROVIDER_TIMEOUT",
                    created_at=now - timedelta(minutes=1),
                ),
                LLMCallLog(
                    user_id=other_user_id,
                    provider_name="other",
                    model="other-model",
                    operation="qa",
                    status="success",
                    total_tokens=999,
                    cost_amount=99,
                    created_at=now,
                ),
            ]
        )
        db.session.commit()

    client = llm_api_app.test_client()
    headers = _headers(llm_api_app, user_id)
    logs = client.get("/api/llm/logs?page=1&per_page=1&model=qwen", headers=headers)
    summary = client.get("/api/llm/logs/summary?model=qwen", headers=headers)
    analytics = client.get("/api/llm/analytics?model=qwen", headers=headers)

    assert logs.status_code == 200
    assert len(logs.json["items"]) == 1
    assert logs.json["total"] == 2
    assert summary.status_code == 200
    assert summary.json["summary"]["total_calls"] == 2
    assert analytics.status_code == 200
    assert analytics.json["summary"]["total_calls"] == 2
    assert all(item["model"] == "qwen" for item in analytics.json["models"])


def test_analytics_report_cache_hit_rate(llm_api_app):
    user_id = _make_user(llm_api_app, "llm-cache-user")
    with llm_api_app.app_context():
        db.session.add(
            LLMCallLog(
                user_id=user_id,
                provider_name="private",
                model="qwen",
                operation="qa",
                status="success",
                input_tokens=100,
                cached_input_tokens=60,
                output_tokens=5,
                total_tokens=105,
                latency_ms=50,
            )
        )
        db.session.commit()

    client = llm_api_app.test_client()
    headers = _headers(llm_api_app, user_id)
    analytics = client.get("/api/llm/analytics", headers=headers)

    assert analytics.status_code == 200
    summary = analytics.json["summary"]
    assert summary["cached_input_tokens"] == 60
    assert summary["cache_hit_rate"] == 60.0
    model_row = analytics.json["models"][0]
    assert model_row["tokens"] == 105
    assert model_row["cache_hit_rate"] == 60.0
    assert model_row["input_tokens"] == 100


def test_analytics_cache_hit_rate_is_null_when_no_input_tokens(llm_api_app):
    user_id = _make_user(llm_api_app, "llm-no-usage-user")
    with llm_api_app.app_context():
        db.session.add(
            LLMCallLog(
                user_id=user_id,
                provider_name="private",
                model="qwen",
                operation="qa",
                status="success",
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=10,
                total_tokens=10,
            )
        )
        db.session.commit()

    client = llm_api_app.test_client()
    headers = _headers(llm_api_app, user_id)
    analytics = client.get("/api/llm/analytics", headers=headers)

    assert analytics.status_code == 200
    assert analytics.json["summary"]["cache_hit_rate"] is None
    assert analytics.json["models"][0]["cache_hit_rate"] is None


def test_provider_delete_is_user_scoped(llm_api_app):
    owner_id = _make_user(llm_api_app, "llm-delete-owner")
    outsider_id = _make_user(llm_api_app, "llm-delete-outsider")
    with llm_api_app.app_context():
        provider = LLMProviderConfig(
            user_id=owner_id,
            name="private",
            base_url="https://llm.example/v1",
            model="private-model",
            api_key_ciphertext="ciphertext",
            api_key_hint="sk-pr••••cret",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id

    response = llm_api_app.test_client().delete(
        f"/api/llm/providers/{provider_id}",
        headers=_headers(llm_api_app, outsider_id),
    )

    assert response.status_code == 404


def test_provider_update_and_test_are_user_scoped(llm_api_app):
    owner_id = _make_user(llm_api_app, "llm-action-owner")
    outsider_id = _make_user(llm_api_app, "llm-action-outsider")
    with llm_api_app.app_context():
        provider = LLMProviderConfig(
            user_id=owner_id,
            name="private",
            base_url="https://llm.example/v1",
            model="private-model",
            api_key_ciphertext="ciphertext",
            api_key_hint="sk-pr••••cret",
        )
        db.session.add(provider)
        db.session.commit()
        provider_id = provider.id

    client = llm_api_app.test_client()
    headers = _headers(llm_api_app, outsider_id)
    updated = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"name": "stolen"},
        headers=headers,
    )
    tested = client.post(f"/api/llm/providers/{provider_id}/test", headers=headers)

    assert updated.status_code == 404
    assert tested.status_code == 404


class _FakeProvider:
    def __init__(self, response):
        self.provider_name = "fake"
        self.base_url = "https://llm.example/v1"
        self.model = "fake-model"
        self._response = response
        self.last_request = None

    def generate(self, request):
        self.last_request = request
        return self._response


def _make_provider_config(application, user_id: int) -> int:
    from app.models.llm import LLMProviderConfig

    with application.app_context():
        provider = LLMProviderConfig(
            user_id=user_id,
            name="fake",
            base_url="https://llm.example/v1",
            model="fake-model",
            api_key_ciphertext="ciphertext",
            api_key_hint="sk-fa••••ket",
        )
        db.session.add(provider)
        db.session.commit()
        return provider.id


def _llm_response(text, *, warning_code=None, finish_reason=None):
    from app.services.llm.contracts import LLMResponse

    return LLMResponse(
        text=text,
        provider_name="fake",
        model="fake-model",
        status_code=200,
        warning_code=warning_code,
        finish_reason=finish_reason,
    )


def test_provider_test_accepts_reasoning_model_output(llm_api_app, monkeypatch):
    from app.routes import llm as llm_routes

    user_id = _make_user(llm_api_app, "llm-reason-ok")
    provider_id = _make_provider_config(llm_api_app, user_id)
    fake = _FakeProvider(_llm_response("OK"))
    monkeypatch.setattr(llm_routes.provider_service, "build_provider", lambda *a, **k: fake)

    response = llm_api_app.test_client().post(
        f"/api/llm/providers/{provider_id}/test",
        headers=_headers(llm_api_app, user_id),
    )

    assert response.status_code == 200
    assert response.get_json()["check"]["status"] == "healthy"
    assert fake.last_request is not None
    assert fake.last_request.max_tokens >= 64


def test_provider_test_reports_truncated_reasoning(llm_api_app, monkeypatch):
    from app.routes import llm as llm_routes

    user_id = _make_user(llm_api_app, "llm-reason-trunc")
    provider_id = _make_provider_config(llm_api_app, user_id)
    fake = _FakeProvider(
        _llm_response(None, warning_code="LLM_OUTPUT_TRUNCATED", finish_reason="length")
    )
    monkeypatch.setattr(llm_routes.provider_service, "build_provider", lambda *a, **k: fake)

    response = llm_api_app.test_client().post(
        f"/api/llm/providers/{provider_id}/test",
        headers=_headers(llm_api_app, user_id),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["check"]["status"] == "LLM_OUTPUT_TRUNCATED"
    assert payload["check"]["warning_code"] == "LLM_OUTPUT_TRUNCATED"
    assert "推理" in payload["check"]["detail"]


def test_provider_max_tokens_persist_and_validate(llm_api_app):
    user_id = _make_user(llm_api_app, "llm-max-tokens")
    client = llm_api_app.test_client()
    headers = _headers(llm_api_app, user_id)

    created = client.post(
        "/api/llm/providers",
        json={
            "name": "with-limit",
            "base_url": "https://llm.internal:8000/v1",
            "model": "deepseek-reasoner",
            "api_key": "sk-test-1",
            "max_tokens": 8192,
        },
        headers=headers,
    )
    assert created.status_code == 201
    provider = created.get_json()["provider"]
    assert provider["max_tokens"] == 8192

    provider_id = provider["id"]
    updated = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"max_tokens": 4096},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()["provider"]["max_tokens"] == 4096

    cleared = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"max_tokens": None},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.get_json()["provider"]["max_tokens"] is None

    invalid = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"max_tokens": 0},
        headers=headers,
    )
    assert invalid.status_code == 400

    invalid_high = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"max_tokens": 1000001},
        headers=headers,
    )
    assert invalid_high.status_code == 400

    million = client.put(
        f"/api/llm/providers/{provider_id}",
        json={"max_tokens": 1000000},
        headers=headers,
    )
    assert million.status_code == 200
    assert million.get_json()["provider"]["max_tokens"] == 1000000


def test_provider_max_tokens_overrides_default_request(llm_api_app, monkeypatch):
    from app.routes import llm as llm_routes

    user_id = _make_user(llm_api_app, "llm-max-override")
    provider_id = _make_provider_config(llm_api_app, user_id)
    with llm_api_app.app_context():
        from app.models.llm import LLMProviderConfig

        provider = db.session.get(LLMProviderConfig, provider_id)
        provider.max_tokens = 8192
        db.session.commit()

    fake = _FakeProvider(_llm_response("OK"))
    monkeypatch.setattr(llm_routes.provider_service, "build_provider", lambda *a, **k: fake)

    response = llm_api_app.test_client().post(
        f"/api/llm/providers/{provider_id}/test",
        headers=_headers(llm_api_app, user_id),
    )

    assert response.status_code == 200
    assert response.get_json()["check"]["status"] == "healthy"
    assert fake.last_request.max_tokens == 512
